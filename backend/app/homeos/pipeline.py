"""HomeOS pipeline: investigate_stream, refine_stream, chat_in_case, and sync helpers."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger("homeos.pipeline")

from app.repositories.base import Repository
from app.homeos import case_store as homeos_case_store
from app.homeos.mock.agents import (
    mock_chat_answer,
    mock_lifestyle_narrative,
    mock_location_narrative,
    mock_market_narrative,
    mock_profile_avatar,
    mock_risk_narrative,
)
from app.homeos.mock.tools import is_mock_mode, mock_delay_seconds
from app.homeos.scoring import worth_viewing_score, _verdict, _confidence, item_texts

FLAT_TYPES = ("2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE")


def _normalise(text: str) -> str:
    return " ".join(text.upper().replace("-", " ").split())


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def _extract_flat_type(text: str) -> str | None:
    norm = _normalise(text)
    compact = norm.replace(" ", "")
    rm_match = re.search(r"\b([2-5])\s*-?\s*(?:rm|room)\b", text, re.IGNORECASE)
    if rm_match:
        return f"{rm_match.group(1)} ROOM"
    bedder_match = re.search(r"\b([2-5])\s*-?\s*(?:bedder|bed)\b", text, re.IGNORECASE)
    if bedder_match and _has_any(text, ("hdb", "flat", "resale")):
        return f"{bedder_match.group(1)} ROOM"
    room_hint = re.search(
        r"\b(?:add|change|switch|make|want|need|looking\s+for|prefer|to|into)\s+(?:a\s+)?([2-5])\b",
        text,
        re.IGNORECASE,
    )
    if room_hint and any(w in text.lower() for w in ("add", "change", "switch", "make", "instead")):
        return f"{room_hint.group(1)} ROOM"
    for flat_type in FLAT_TYPES:
        if flat_type in norm:
            return flat_type
    if room_hint:
        return f"{room_hint.group(1)} ROOM"
    if "2ROOM" in compact:
        return "2 ROOM"
    if "2RM" in compact:
        return "2 ROOM"
    if "3ROOM" in compact:
        return "3 ROOM"
    if "3RM" in compact:
        return "3 ROOM"
    if "4ROOM" in compact:
        return "4 ROOM"
    if "4RM" in compact:
        return "4 ROOM"
    if "5ROOM" in compact:
        return "5 ROOM"
    if "5RM" in compact:
        return "5 ROOM"
    if "EXEC" in compact:
        return "EXECUTIVE"
    return None


def _extract_town(text: str) -> str | None:
    towns = _extract_towns(text)
    return towns[0] if towns else None


def _extract_towns(text: str) -> list[str]:
    from app.homeos.tools.search import _fuzzy_match_town

    cleaned = re.sub(r"[^A-Za-z0-9 -]+", " ", text.upper().replace("/", " "))
    words = cleaned.split()
    ambiguous_singletons = {
        "EAST", "WEST", "NORTH", "SOUTH", "NORTHEAST", "NORTHWEST",
        "SOUTHEAST", "SOUTHWEST",
    }
    negative_markers = {"NO", "NOT", "AVOID", "EXCLUDE", "EXCLUDING", "WITHOUT"}
    matches: list[tuple[int, int, str]] = []
    for i in range(len(words)):
        if any(marker in words[max(0, i - 2):i] for marker in negative_markers):
            continue
        for length in (3, 2, 1):
            if i + length > len(words):
                continue
            phrase = " ".join(words[i:i + length])
            if length == 1 and phrase in ambiguous_singletons:
                continue
            town = _fuzzy_match_town(phrase)
            if town:
                matches.append((i, length, town.value))
                break
    towns: list[str] = []
    consumed: set[int] = set()
    for i, length, town in sorted(matches, key=lambda x: (x[0], -x[1])):
        span = set(range(i, i + length))
        if consumed & span:
            continue
        consumed |= span
        if town not in towns:
            towns.append(town)
    return towns


def _extract_budget(text: str) -> float | None:
    lowered = text.lower().replace(",", "")
    patterns = [
        r"(?:under|below|up to|max|maximum|budget)\s*\$?\s*(\d+(?:\.\d+)?)\s*(m|mil|million|k)?",
        r"(?:around|about|stretch to|can stretch to)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:-?\s*ish)?\s*(m|mil|million|k)?",
        r"\$?\s*(\d+(?:\.\d+)?)\s*(?:-?\s*ish)\b",
        r"\$?\s*(\d+(?:\.\d+)?)\s*(m|mil|million|k)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        value = float(match.group(1))
        suffix = match.group(2)
        if suffix in {"m", "mil", "million"}:
            return value * 1_000_000
        if suffix == "k":
            return value * 1_000
        if value < 10_000:
            return value * 1_000
        return value
    word_numbers = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9,
    }
    word_match = re.search(
        r"(?:budget|under|below|up to|max|maximum|around|about)?\s*"
        r"(one|two|three|four|five|six|seven|eight|nine)\s+hundred\s+k\b",
        lowered,
    )
    if word_match:
        return float(word_numbers[word_match.group(1)] * 100_000)
    return None


def _is_estate_related_text(text: str) -> bool:
    lowered = text.lower()
    estate_terms = (
        "hdb", "bto", "resale", "private", "condo", "apartment", "flat",
        "room", "executive", "budget", "price", "psf", "mrt", "school",
        "commute", "bus", "town", "estate", "block", "lease", "viewing",
        "agent", "listing", "home", "house", "property", "serangoon",
        "tampines", "bishan", "queenstown", "toa payoh", "punggol",
        "sengkang", "bedok", "yishun", "woodlands", "jurong",
    )
    return any(term in lowered for term in estate_terms) or _extract_flat_type(text) is not None or _extract_town(text) is not None


def _extract_work_locations(text: str) -> list[str]:
    locations: list[str] = []
    patterns = (
        re.compile(
            r"\b(?:i|me|we)\s+(?:work|works|working|office)\s+(?:(?:at|in|near)\s+)?"
            r"([A-Za-z][A-Za-z0-9 .'-]*?)(?=\s+(?:and|with|but|because|while|plus|wife|husband|partner|spouse|he|she)\b|[.,;]|$)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:work|works|working|office)\s+(?:at|in|near)\s+"
            r"([A-Za-z][A-Za-z0-9 .'-]*?)(?=\s+(?:and|with|but|because|while|plus|wife|husband|partner|spouse|he|she)\b|[.,;]|$)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:i|me|we)\s+(?:at|in|near)\s+"
            r"([A-Za-z][A-Za-z0-9 .'-]*?)(?=\s+(?:and|with|but|because|while|plus|wife|husband|partner|spouse|he|she)\b|[.,;]|$)",
            re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        for match in pattern.finditer(text):
            loc = " ".join(match.group(1).split()).strip(" .,-")
            if loc and loc.casefold() not in {x.casefold() for x in locations}:
                locations.append(loc)
    return locations


def _remove_work_location_clauses(text: str) -> str:
    patterns = (
        r"\b(?:(?:i|me|we|partner|wife|husband|spouse|he|she)\s+)"
        r"(?:(?:work|works|working|office)\s+(?:(?:at|in|near)\s+)?|(?:at|in|near)\s+)"
        r"[A-Za-z][A-Za-z0-9 .'-]*?(?=\s+(?:and|with|but|because|while|plus|wife|husband|partner|spouse|he|she)\b|[.,;]|$)",
        r"\b(?:work|works|working|office)\s+(?:at|in|near)\s+"
        r"[A-Za-z][A-Za-z0-9 .'-]*?(?=\s+(?:and|with|but|because|while|plus|wife|husband|partner|spouse|he|she)\b|[.,;]|$)",
    )
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _school_need_negated(text: str) -> bool:
    return _has_any(
        text,
        (
            "no kids", "no children", "without kids", "without children",
            "no need school", "no need schools", "no schools", "school not important",
            "schools not important", "don't need school", "don't need schools",
            "dont need school", "dont need schools", "not near school", "not near schools",
        ),
    )


def _extract_partner_work_locations(text: str) -> list[str]:
    """Extract workplace locations for the partner/spouse in couple mode."""
    locations: list[str] = []
    pattern = re.compile(
        r"\b(?:partner|wife|husband|spouse|he|she)\s+(?:(?:works?|office)\s+(?:(?:at|in|near)\s+)?|(?:at|in|near)\s+)"
        r"([A-Za-z][A-Za-z0-9 .'-]*?)(?=\s+(?:and|with|but|because|while|plus)\b|[.,;]|$)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        loc = " ".join(match.group(1).split()).strip(" .,-")
        if loc and loc.casefold() not in {x.casefold() for x in locations}:
            locations.append(loc)
    return locations


def parse_homeos_profile(profile_text: str) -> dict[str, Any]:
    is_couple = _has_any(profile_text, ("partner", "wife", "husband", "spouse", "couple", "together", "both of us", "the two of us"))
    school_negated = _school_need_negated(profile_text)
    buyer_type = "family" if (not school_negated and _has_any(profile_text, ("family", "kids", "children", "child", "primary school", "schools"))) else ("couple" if is_couple else "single")
    if _has_any(profile_text, ("must be close to mrt", "near mrt", "close to mrt", "mrt access", "within 600", "close to train", "near train", "train access")) or (
        "mrt" in profile_text.lower() and "close" in profile_text.lower()
    ):
        commute_priority = "high"
    elif _has_any(profile_text, ("medium commute", "1.2km", "1200", "moderate commute", "within 1.2", "within 1km of mrt",
                                  "works in", "work in", "office in", "workplace", "cbd", "raffles place", "tanjong pagar",
                                  "city hall", "marina bay", "one north", "jurong east")):
        commute_priority = "medium"
    else:
        commute_priority = "low"
    school_priority = "high" if (not school_negated and _has_any(profile_text, ("primary school", "schools", "kids", "children", "family"))) else "low"
    risk_tolerance = "medium" if _has_any(profile_text, ("some risk", "appreciation risk", "growth", "invest")) else "low"
    appreciation_priority = "high" if _has_any(profile_text, ("growth", "appreciation", "investment", "undervalued")) else "medium"
    work_locations = _extract_work_locations(profile_text)
    partner_work_locations = _extract_partner_work_locations(profile_text) if is_couple else []
    bus_reliance = "high" if _has_any(
        profile_text,
        ("no car", "without a car", "don't drive", "doesn't drive", "depend on bus", "depends on bus",
         "dont drive", "doesnt drive", "do not drive", "not driving", "depend on buses", "depends on buses",
         "rely on bus", "rely on buses", "bus dependent", "near bus", "bus access"),
    ) else "low"
    if buyer_type == "family":
        label = "Family HomeOS Agent"
        summary = "Family buyer prioritizing schools, budget fit, and lower-risk viewing choices."
    elif buyer_type == "couple":
        label = "Couple HomeOS Agent"
        summary = "Couple buyer balancing commute fairness, affordability, and accessibility."
    elif commute_priority == "high":
        label = "Commute HomeOS Agent"
        summary = "Commute-focused buyer prioritizing MRT access and practical viewing choices."
    else:
        label = "Careful HomeOS Agent"
        summary = "Careful buyer balancing affordability, accessibility, and resale evidence."
    return {
        "label": label,
        "buyer_type": buyer_type,
        "summary": summary,
        "preferences": {
            "flat_type": _extract_flat_type(profile_text),
            "max_price": _extract_budget(profile_text),
            "town": _extract_town(_remove_work_location_clauses(profile_text)),
            "preferred_towns": _extract_towns(_remove_work_location_clauses(profile_text)),
            "commute_priority": commute_priority,
            "school_priority": school_priority,
            "risk_tolerance": risk_tolerance,
            "appreciation_priority": appreciation_priority,
            "work_locations": work_locations,
            "partner_work_locations": partner_work_locations,
            "bus_reliance": bus_reliance,
        },
    }


# ── Registry-backed agent runner ──────────────────────────────────────────────

def _apply_rule_profile_fallback(avatar_dict: dict[str, Any], profile_text: str) -> dict[str, Any]:
    """Merge deterministic estate parsing into a profile-agent result."""
    fallback = parse_homeos_profile(profile_text)
    fallback_prefs = fallback.get("preferences", {})
    prefs = {**fallback_prefs, **(avatar_dict.get("preferences") or {})}

    for field in (
        "flat_type", "max_price", "town", "preferred_towns", "min_schools_within_1km",
        "work_locations", "partner_work_locations",
    ):
        value = fallback_prefs.get(field)
        if value not in (None, "", []):
            prefs[field] = value

    for field, default in (
        ("commute_priority", "low"),
        ("school_priority", "low"),
        ("risk_tolerance", "low"),
        ("appreciation_priority", "medium"),
        ("bus_reliance", "low"),
    ):
        value = fallback_prefs.get(field)
        if value != default:
            prefs[field] = value

    merged = dict(avatar_dict)
    merged["preferences"] = prefs
    if not merged.get("summary"):
        merged["summary"] = fallback.get("summary", "")
    if merged.get("label") in (None, "", "HomeOS Agent"):
        merged["label"] = fallback.get("label", "HomeOS Agent")
    if merged.get("buyer_type") in (None, "", "single") and fallback.get("buyer_type") != "single":
        merged["buyer_type"] = fallback["buyer_type"]
    return merged


async def _run_profile_agent(prompt: str, model_override: str | None = None):
    """Run the profile agent via the tool repository. Returns (HomeOSAvatar, {}, result)."""
    from app.homeos.wiring import tool_repository
    agent, prefetched = tool_repository.build_agent("profile", repo=None, block_id=None, prefs={}, model_override=model_override)
    result = await agent.run(prompt)
    return result.output, prefetched, result


async def _run_block_agent(name: str, repo: Repository, block_id: int, prefs: dict, prompt: str, model_override: str | None = None):
    """Run a named block-level agent. Returns (output_model, prefetched_dict, result)."""
    from app.homeos.wiring import tool_repository
    agent, prefetched = tool_repository.build_agent(name, repo=repo, block_id=block_id, prefs=prefs, model_override=model_override)
    result = await agent.run(prompt)
    return result.output, prefetched, result


def _extract_tool_calls(result) -> list[dict]:
    """Extract tool calls from pydantic-ai result.all_messages().

    Filters out pydantic-ai's internal 'final_result' tool which is used
    for structured output, not an actual user-defined tool.
    """
    from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart

    tool_calls = []
    tool_returns = {}

    try:
        for msg in result.all_messages():
            # Look for ToolCallPart in ModelResponse
            if isinstance(msg, ModelResponse):
                for part in msg.parts:
                    if isinstance(part, ToolCallPart):
                        # Skip pydantic-ai's internal final_result tool
                        if part.tool_name == "final_result":
                            continue
                        tool_calls.append({
                            "tool_name": part.tool_name,
                            "args": part.args,
                            "tool_call_id": part.tool_call_id,
                        })

            # Look for ToolReturnPart in ModelRequest
            elif isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if isinstance(part, ToolReturnPart):
                        tool_returns[part.tool_call_id] = part.content

        # Match tool calls with their returns
        for call in tool_calls:
            call_id = call.pop("tool_call_id", None)
            if call_id and call_id in tool_returns:
                call["result"] = tool_returns[call_id]

    except Exception as e:
        logger.warning("Failed to extract tool calls: %s", e)

    return tool_calls


# ── Lifestyle helpers ─────────────────────────────────────────────────────────

def _build_lifestyle_inputs(repo: Repository, prefs: dict):
    """Return (provider, destinations) from prefs work_locations, or (None, None)."""
    from app.services.commute.models import Destination
    from app.services.commute.provider import HeuristicCommuteProvider
    from app.homeos.tools.commute import _resolve_station

    workplaces = prefs.get("work_locations") or []
    stations = list(repo.mrt_stations(status="operational"))
    if not stations:
        return None, None

    provider = HeuristicCommuteProvider(stations)
    destinations = []
    for name in workplaces:
        station = _resolve_station(str(name), stations)
        if station is not None:
            destinations.append(Destination(name=station.station_name, point=station.point, visits_per_week=5))

    return provider, destinations or None


# ── Per-agent evidence builders ────────────────────────────────────────────────
# Each returns (evidence_dict, tool_calls). Pulled out of the stream loop so the
# four block subagents can run concurrently instead of one-after-another.

async def _compute_market_evidence(repo: Repository, block_id: int, prefs: dict, mock: bool, model_override: str | None):
    from app.homeos.wiring import tool_repository
    if mock:
        # Prefetch data and use the deterministic mock narrative.
        _, prefetched = tool_repository.build_agent("market", repo=repo, block_id=block_id, prefs=prefs)
        txn_data = prefetched.get("transactions", {})
        return {**txn_data, "narrative": mock_market_narrative(txn_data, prefs)}, []
    output, _, result = await _run_block_agent(
        "market", repo, block_id, prefs,
        "Analyze market evidence for this block using the available tools.",
        model_override,
    )
    return output.model_dump(), _extract_tool_calls(result)


async def _compute_location_evidence(repo: Repository, block_id: int, prefs: dict, mock: bool, model_override: str | None):
    from app.homeos.wiring import tool_repository
    if mock:
        _, prefetched = tool_repository.build_agent("location", repo=repo, block_id=block_id, prefs=prefs)
        prox_data = prefetched.get("proximity", {})
        connections = prox_data.get("connections", [])
        return {**prox_data, "narrative": mock_location_narrative(connections)}, []
    output, _, result = await _run_block_agent(
        "location", repo, block_id, prefs,
        "Analyze location and connectivity for this block using the available tools.",
        model_override,
    )
    return output.model_dump(), _extract_tool_calls(result)


async def _compute_risk_evidence(repo: Repository, block_id: int, prefs: dict, mock: bool, model_override: str | None):
    from app.homeos.wiring import tool_repository
    if mock:
        # Prefetch data and compute watchouts / score adjustment manually.
        _, prefetched = tool_repository.build_agent("risk", repo=repo, block_id=block_id, prefs=prefs)
        app_data = prefetched.get("appreciation", {})
        future_dev_data = prefetched.get("future_dev", {})
        future_supply_data = future_dev_data.get("future_supply", {})
        watchouts: list[str] = []
        score_adjustment = 0.0
        if app_data.get("appreciation_score") is not None:
            score_adjustment += min(12.0, app_data["appreciation_score"] / 10)
        if app_data.get("risk_level") == "high" and prefs.get("risk_tolerance") == "low":
            watchouts.append("Appreciation model flags elevated risk for a low-risk buyer.")
            score_adjustment -= 8.0
        if future_supply_data.get("supply_risk_level") == "high":
            watchouts.append("Nearby future supply may weigh on appreciation.")
            score_adjustment -= 4.0
        return {
            "appreciation": app_data,
            "future_mrt": future_dev_data.get("future_mrt"),
            "future_supply": future_supply_data,
            "watchouts": watchouts,
            "score_adjustment": score_adjustment,
            "narrative": mock_risk_narrative({"watchouts": watchouts, "score_adjustment": score_adjustment}),
        }, []
    output, _, result = await _run_block_agent(
        "risk", repo, block_id, prefs,
        f"Analyze risk factors for this block. Buyer risk_tolerance: {prefs.get('risk_tolerance', 'low')}",
        model_override,
    )
    return output.model_dump(), _extract_tool_calls(result)


async def _compute_lifestyle_evidence(repo: Repository, block_id: int, prefs: dict, mock: bool):
    if mock:
        ls_data = {
            "lifestyle_score": None,
            "commute_band": None,
            "couple_fairness": None,
            "factors": {},
            "watchouts": [],
        }
        ls_data["narrative"] = mock_lifestyle_narrative(ls_data)
        return ls_data, []
    output, _, result = await _run_block_agent(
        "lifestyle", repo, block_id, prefs,
        "Analyze lifestyle fit for this block using the available tools.",
    )
    return output.model_dump(), _extract_tool_calls(result)


async def _compute_mock_evidence(agent_name: str, repo: Repository, block_id: int, prefs: dict) -> dict:
    if agent_name == "market":
        evidence, _ = await _compute_market_evidence(repo, block_id, prefs, True, None)
    elif agent_name == "location":
        evidence, _ = await _compute_location_evidence(repo, block_id, prefs, True, None)
    elif agent_name == "risk":
        evidence, _ = await _compute_risk_evidence(repo, block_id, prefs, True, None)
    elif agent_name == "lifestyle":
        evidence, _ = await _compute_lifestyle_evidence(repo, block_id, prefs, True)
    else:
        evidence = {"narrative": ""}
    evidence["model_fallback"] = True
    return evidence


# Sentinel pushed onto the per-block event queue when one subagent finishes.
_AGENT_DONE = object()


async def _stream_agent(name: str, queue: asyncio.Queue, block_id: int, mock: bool, compute):
    """Run one block subagent, pushing its SSE events onto `queue`; return its evidence.

    Emits the same event sequence the sequential pipeline did
    (agent_start → [tool_calls] → agent_data → agent_summary → agent_done) so the
    frontend, which keys events by (agent, block_id), is unchanged.
    """
    await queue.put({"event": "agent_start", "agent": name, "block_id": block_id})
    if mock:
        await asyncio.sleep(mock_delay_seconds())
    evidence, tool_calls = await compute()
    if tool_calls:
        await queue.put({"event": "tool_calls", "agent": name, "block_id": block_id, "tool_calls": tool_calls})
    await queue.put({"event": "agent_data", "agent": name, "block_id": block_id, "data": evidence})
    await queue.put({"event": "agent_summary", "agent": name, "block_id": block_id, "narrative": evidence.get("narrative", "")})
    await queue.put({"event": "agent_done", "agent": name, "block_id": block_id})
    return evidence


# ── Deep analysis ─────────────────────────────────────────────────────────────

async def _deep_analysis_stream(
    repo: Repository,
    case_id: str,
    candidates: list[dict],
    prefs: dict,
    model_override: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Phase 3: run market/location/risk agents on each candidate via registry."""
    rows = []
    for candidate in candidates:
        block_id = candidate["block_id"]
        mock = is_mock_mode()

        # The four block subagents are independent, so run them concurrently and
        # stream their events through a shared queue as each is produced. Blocks
        # are still processed one at a time, which bounds gateway load.
        agent_specs = (
            ("market", lambda: _compute_market_evidence(repo, block_id, prefs, mock, model_override)),
            ("location", lambda: _compute_location_evidence(repo, block_id, prefs, mock, model_override)),
            ("risk", lambda: _compute_risk_evidence(repo, block_id, prefs, mock, model_override)),
            ("lifestyle", lambda: _compute_lifestyle_evidence(repo, block_id, prefs, mock)),
        )
        queue: asyncio.Queue = asyncio.Queue()
        results: dict[str, dict] = {}
        errors: list[Exception] = []

        async def _worker(agent_name, compute):
            try:
                results[agent_name] = await _stream_agent(agent_name, queue, block_id, mock, compute)
            except Exception as exc:  # one failing agent shouldn't wedge the block
                logger.warning(
                    "[case:%s] %s model failed for block %d; using deterministic fallback: %s",
                    case_id[:8], agent_name, block_id, exc,
                )
                try:
                    evidence = await _compute_mock_evidence(agent_name, repo, block_id, prefs)
                    results[agent_name] = evidence
                    await queue.put({"event": "agent_data", "agent": agent_name, "block_id": block_id, "data": evidence})
                    await queue.put({
                        "event": "agent_summary",
                        "agent": agent_name,
                        "block_id": block_id,
                        "narrative": evidence.get("narrative", ""),
                    })
                    await queue.put({"event": "agent_done", "agent": agent_name, "block_id": block_id})
                except Exception as fallback_exc:
                    errors.append(fallback_exc)
            finally:
                await queue.put(_AGENT_DONE)

        tasks = [asyncio.create_task(_worker(name, compute)) for name, compute in agent_specs]

        # Drain events in real time as the concurrent agents emit them. Each
        # worker pushes exactly one _AGENT_DONE sentinel when it finishes.
        remaining = len(agent_specs)
        while remaining:
            evt = await queue.get()
            if evt is _AGENT_DONE:
                remaining -= 1
                continue
            yield evt
            homeos_case_store.append_event(case_id, evt)

        await asyncio.gather(*tasks)

        if errors:
            # Match the previous behaviour: skip a block whose analysis failed.
            logger.warning("[case:%s] agent error for block %d: %s — skipping", case_id[:8], block_id, errors[0])
            continue

        market_evidence = results.get("market", {})
        location_evidence = results.get("location", {})
        risk_evidence = results.get("risk", {})
        lifestyle_evidence = results.get("lifestyle", {})

        txn_count = market_evidence.get("transaction_count", 0)
        score, reasons, watchouts = worth_viewing_score(market_evidence, location_evidence, risk_evidence, prefs, lifestyle_evidence)
        logger.info(
            "[case:%s] SCORED block_id=%d  score=%.1f  verdict=%s  txn=%d",
            case_id[:8], block_id, score, _verdict(score), txn_count,
        )
        rows.append({
            "block_id": block_id,
            "block_number": candidate["block_number"],
            "street_name": candidate["street_name"],
            "town": candidate["town"],
            "worth_viewing_score": score,
            "verdict": _verdict(score),
            "confidence": _confidence(txn_count),
            "top_reasons": reasons,
            "top_watchouts": watchouts,
            "lifestyle_score": lifestyle_evidence.get("lifestyle_score"),
            "commute_band": lifestyle_evidence.get("commute_band"),
        })

    rows.sort(key=lambda r: (-r["worth_viewing_score"], r["block_id"]))
    homeos_case_store.set_shortlist(case_id, rows)
    homeos_case_store.set_status(case_id, "done")
    logger.info("[case:%s] DONE  shortlist=%d", case_id[:8], len(rows))

    done_evt = {"event": "case_done", "case_id": case_id, "shortlist": rows}
    yield done_evt
    homeos_case_store.append_event(case_id, done_evt)


# ── Search phase helpers ───────────────────────────────────────────────────────

def _prefs_to_search_query(
    prefs: dict,
    candidate_limit: int = 100,
    town_override: str | None = None,
    relax: set[str] | None = None,
):
    from app.core.models import SearchQuery
    relax = relax or set()
    school = prefs.get("school_priority", "low")
    min_schools = prefs.get("min_schools_within_1km")
    if min_schools is None:
        if school == "high":
            min_schools = 2
        elif school == "medium":
            min_schools = 1
    if "schools" in relax or "proximity" in relax:
        min_schools = None
    # Only hard-filter by MRT when the buyer explicitly stated a preference.
    # "low" is the implicit default — zero filter applied when commute was never mentioned.
    commute = prefs.get("commute_priority", "low")
    if "mrt" in relax or "proximity" in relax:
        max_mrt_distance_m = None
    elif commute == "high":
        max_mrt_distance_m = 600.0
    elif commute == "medium":
        max_mrt_distance_m = 1200.0
    else:
        max_mrt_distance_m = None

    # Filter by bus stop distance when buyer is bus-dependent
    bus_reliance = prefs.get("bus_reliance", "low")
    max_bus_distance_m = None if ("bus" in relax or "proximity" in relax) else (400.0 if bus_reliance == "high" else None)

    return SearchQuery(
        flat_type=None if "flat_type" in relax else prefs.get("flat_type"),
        max_price=None if "max_price" in relax else prefs.get("max_price"),
        town=None if "town" in relax else (town_override if town_override is not None else prefs.get("town")),
        max_mrt_distance_m=max_mrt_distance_m,
        max_bus_distance_m=max_bus_distance_m,
        min_schools_within_1km=min_schools,
        limit=candidate_limit,
    )


def _lightweight_rank(candidates: list[dict], prefs: dict, top_n: int) -> list[dict]:
    commute = prefs.get("commute_priority", "low")
    school = prefs.get("school_priority", "low")
    max_price = prefs.get("max_price")

    def _score(c: dict) -> float:
        s = 0.0
        mrt = c.get("nearest_mrt_distance_m") or 9999
        if mrt <= 400:
            s += 40 if commute == "high" else 20
        elif mrt <= 800:
            s += 25 if commute == "high" else 15
        elif mrt <= 1200:
            s += 10
        schools = c.get("schools_within_1km") or 0
        if schools >= 2:
            s += 30 if school == "high" else 10
        elif schools == 1:
            s += 15 if school == "high" else 5
        med = c.get("median_price")
        if max_price and med:
            headroom = (max_price - med) / max_price
            if headroom >= 0.1:
                s += 20
            elif headroom >= 0:
                s += 10
        txn = c.get("txn_count") or 0
        if txn >= 6:
            s += 10
        elif txn >= 3:
            s += 5
        return s

    return sorted(candidates, key=_score, reverse=True)[:top_n]


_ANALYSIS_THRESHOLD = 5
_SOFT_THRESHOLD = 5


_PROCEED_PHRASES = {
    "proceed", "go ahead", "continue", "analyse", "analyze",
    "just proceed", "proceed please", "lets go", "let's go", "go",
}


def _is_proceed_intent(message: str) -> bool:
    """True when the user wants to skip remaining questions and analyse now.

    The clarifying prompts explicitly tell users to "say 'proceed'", so this
    must be honoured wherever a refinement answer arrives.
    """
    m = (message or "").strip().lower().rstrip(" .!")
    return m in _PROCEED_PHRASES or m.startswith("proceed")


def _ready_to_proceed_question(count: int) -> str:
    """Confirm prompt shown once a result set is small enough to analyse.

    Surfaced with a single 'Proceed' quick-reply chip on the frontend
    (field='ready_to_proceed'); the user can also keep refining instead.
    """
    blocks = "block" if count == 1 else "blocks"
    return (
        f"Ready to analyse {count} {blocks}? "
        "Tap Proceed to start, or keep refining."
    )


def _no_candidates_question() -> str:
    return (
        "I found 0 matching blocks with those filters. "
        "Would you like to loosen the budget, choose any town, or change the flat type?"
    )


def _clarifying_question(
    prefs: dict, count: int, pipeline: list[dict] | None = None
) -> tuple[str | None, str | None]:
    already_asked: set[str] = {
        e["field"]
        for e in (pipeline or [])
        if e.get("event") == "clarifying_question" and e.get("field")
    }
    if not prefs.get("flat_type") and "flat_type" not in already_asked:
        return (
            f"I found {count} matching properties. "
            "What type of flat are you looking for — 2-room, 3-room, 4-room, 5-room, or Executive?",
            "flat_type",
        )
    if not prefs.get("max_price") and "max_price" not in already_asked:
        return (
            f"I found {count} flats. "
            "What's your maximum budget? (e.g. $600k, $700k, $800k, $1M)",
            "max_price",
        )
    if prefs.get("commute_priority", "low") not in ("medium", "high") and "commute_priority" not in already_asked:
        return (
            f"Still {count} options. How important is being close to an MRT? "
            "High = within 600 m, Medium = within 1.2 km.",
            "commute_priority",
        )
    if prefs.get("school_priority", "low") == "low" and "school_priority" not in already_asked:
        return (
            f"Still {count} options. Do you need primary schools nearby? "
            "High = 2+ within 1 km, Medium = 1+ within 1 km.",
            "school_priority",
        )
    if not prefs.get("town") and "town" not in already_asked:
        return (
            f"Still {count} options — quite a lot! "
            "Could you name a preferred town or estate? (e.g. Tampines, Bishan, Toa Payoh, Jurong East)",
            "town",
        )
    if count > _SOFT_THRESHOLD and "open_ended" not in already_asked:
        return (
            f"Still {count} options after applying your preferences. "
            "Anything else you'd like — a price range, a specific flat type, or another town? "
            "Or say 'proceed' and I'll analyse the best matches from what we have.",
            "open_ended",
        )
    return (None, None)


def _preference_review(
    query_dict: dict, prefs: dict, count: int, pipeline: list[dict] | None = None
) -> tuple[str | None, str | None]:
    """Ask one missing preference dimension at a time before deep analysis.

    Replaces the old multi-bullet consolidated gate. Each dimension tracks its
    own field in the pipeline asked-set, so no "preference_review" sentinel is needed.
    """
    from app.homeos.wiring import tool_repository

    asked: set[str] = {
        e["field"]
        for e in (pipeline or [])
        if e.get("event") == "clarifying_question" and e.get("field")
    }

    for dim in tool_repository.review_dimensions():
        if dim.field in asked:
            continue
        if dim.query_key is not None:
            if dim.query_key in query_dict:
                continue
        elif dim.default is not None:
            if prefs.get(dim.field, dim.default) != dim.default:
                continue

        result_label = (
            f"{count} options" if count > _ANALYSIS_THRESHOLD else f"{count} blocks"
        )
        question = (
            f"I've narrowed it to {result_label}. "
            f"{dim.question} You can also say 'proceed' and I'll analyse as-is."
        )
        return (question, dim.field)

    return (None, None)


def _build_refinement_prompt(case: dict) -> str:
    questions = [
        e["question"]
        for e in case.get("pipeline", [])
        if e.get("event") == "clarifying_question" and e.get("question")
    ]
    user_answers = [
        m["content"] for m in case.get("conversation", []) if m["role"] == "user"
    ]
    qa_lines: list[str] = []
    for i, q in enumerate(questions):
        answer = user_answers[i] if i < len(user_answers) else "(no answer yet)"
        qa_lines.append(f"Q: {q}\nA: {answer}")
    qa_block = "\n\n".join(qa_lines)
    return (
        f"Buyer profile: {case['profile_text']}\n\n"
        + (f"Clarifying Q&A:\n{qa_block}\n\n" if qa_block else "")
        + "Extract ALL constraints — including the answers above — into HomeOSPreferences."
    )


def _direct_answer_overrides(user_message: str, pipeline: list[dict]) -> dict:
    last_q = next(
        (e.get("question", "") for e in reversed(pipeline) if e.get("event") == "clarifying_question"),
        None,
    )
    if not last_q:
        return {}
    lower_q = last_q.lower()
    lower_a = user_message.lower().strip()
    updates: dict = {}

    explicit_flat_type = _extract_flat_type(user_message)
    if explicit_flat_type:
        updates["flat_type"] = explicit_flat_type

    explicit_budget = _extract_budget(user_message)
    if explicit_budget:
        updates["max_price"] = explicit_budget

    explicit_towns = _extract_towns(user_message)
    if explicit_towns:
        updates["town"] = explicit_towns[0]
        updates["preferred_towns"] = explicit_towns

    if any(phrase in lower_a for phrase in ("any town", "all towns", "no town", "remove town", "drop town")):
        updates["town"] = None
        updates["preferred_towns"] = []
    if any(phrase in lower_a for phrase in ("any flat", "any room", "remove flat", "drop flat", "remove room")):
        updates["flat_type"] = None
    if any(phrase in lower_a for phrase in ("no budget", "remove budget", "drop budget", "any budget")):
        updates["max_price"] = None

    if "flat type" in lower_q or "room" in lower_q:
        pass
    elif "budget" in lower_q or "maximum" in lower_q:
        pass
    elif "mrt" in lower_q or "commute" in lower_q:
        if any(w in lower_a for w in ("high", "600", "very", "yes", "close", "important", "definitely", "must")):
            updates["commute_priority"] = "high"
        elif any(w in lower_a for w in ("medium", "1200", "1.2", "moderate", "somewhat", "ok", "okay", "fine")):
            updates["commute_priority"] = "medium"
        elif any(w in lower_a for w in ("low", "no", "not", "don't", "doesn't", "not really", "not important")):
            updates["commute_priority"] = "low"
    elif "school" in lower_q:
        if any(w in lower_a for w in ("high", "yes", "important", "definitely", "2", "two", "multiple")):
            updates["school_priority"] = "high"
        elif any(w in lower_a for w in ("medium", "one", "1", "some")):
            updates["school_priority"] = "medium"
        elif any(w in lower_a for w in ("low", "no", "not", "don't", "doesn't")):
            updates["school_priority"] = "low"
    elif "town" in lower_q or "estate" in lower_q:
        pass
    elif "work" in lower_q or "workplace" in lower_q or "commute" in lower_q:
        # Extract work locations from the answer
        work_locs = _extract_work_locations(user_message)
        if work_locs:
            updates["work_locations"] = work_locs
    elif "bus" in lower_q or "car" in lower_q:
        # Check if they rely on buses
        if any(w in lower_a for w in ("yes", "high", "no car", "rely", "depend", "bus")):
            updates["bus_reliance"] = "high"
        elif any(w in lower_a for w in ("no", "low", "have car", "drive", "car owner")):
            updates["bus_reliance"] = "low"
    return updates


def _normalise_town_list(prefs: dict) -> list[str | None]:
    towns: list[str] = []
    for raw in prefs.get("preferred_towns") or []:
        value = raw.value if hasattr(raw, "value") else str(raw)
        if value and value not in towns:
            towns.append(value)
    town = prefs.get("town")
    if town:
        value = town.value if hasattr(town, "value") else str(town)
        if value not in towns:
            towns.insert(0, value)
    return towns or [None]


def _query_dict(search_q, towns: list[str | None], relax: set[str] | None = None) -> dict:
    import dataclasses

    result = {
        k: v for k, v in dataclasses.asdict(search_q).items()
        if v is not None and k != "limit"
    }
    concrete_towns = [t for t in towns if t]
    if len(concrete_towns) > 1 and "town" not in (relax or set()):
        result.pop("town", None)
        result["preferred_towns"] = concrete_towns
    return result


async def _run_search_variant(
    repo: Repository,
    prefs: dict,
    candidate_limit: int,
    relax: set[str] | None = None,
) -> tuple[list[dict], dict]:
    from app.services.search import search_blocks

    relax = relax or set()
    towns = [None] if "town" in relax else _normalise_town_list(prefs)
    merged: dict[int, dict] = {}
    first_query = None
    for town in towns:
        search_q = _prefs_to_search_query(
            prefs,
            candidate_limit=candidate_limit,
            town_override=town,
            relax=relax,
        )
        if first_query is None:
            first_query = search_q
        for candidate in await asyncio.to_thread(search_blocks, repo, search_q):
            merged.setdefault(candidate["block_id"], candidate)

    candidates = list(merged.values())
    candidates.sort(key=lambda r: (r.get("median_psf") is None, r.get("median_psf") or 0.0, r["block_id"]))
    return candidates[:candidate_limit], _query_dict(first_query, towns, relax)


async def _search_phase(
    repo: Repository,
    case_id: str,
    prefs: dict,
) -> tuple[list[dict], list[dict], dict]:
    candidates, query_dict = await _run_search_variant(repo, prefs, candidate_limit=500)
    strict_query = dict(query_dict)
    if not candidates:
        relaxation_plan: list[tuple[str, set[str], str]] = [
            ("relaxed_proximity", {"proximity"}, "Relaxed school, MRT, and bus distance filters."),
            ("relaxed_budget", {"proximity", "max_price"}, "Relaxed proximity and budget filters."),
            ("relaxed_town", {"proximity", "town"}, "Relaxed proximity and preferred town filters."),
            ("relaxed_budget_and_town", {"proximity", "max_price", "town"}, "Relaxed proximity, budget, and town filters."),
            ("relaxed_flat_type", {"proximity", "max_price", "town", "flat_type"}, "Relaxed all hard filters except the result limit."),
        ]
        for relaxation_id, relax, message in relaxation_plan:
            candidates, relaxed_query = await _run_search_variant(repo, prefs, candidate_limit=500, relax=relax)
            if candidates:
                query_dict = {
                    **relaxed_query,
                    "strict_query": strict_query,
                    "relaxation_applied": relaxation_id,
                    "relaxation_message": message,
                }
                break
    logger.info(
        "[case:%s] search returned %d candidates  query=%s",
        case_id[:8], len(candidates), query_dict,
    )
    ranked = _lightweight_rank(candidates, prefs, top_n=_ANALYSIS_THRESHOLD)
    return candidates, ranked, query_dict


def _add_skipped_fields(query_dict: dict, pipeline: list[dict]) -> dict:
    _field_to_query_key = {"flat_type": "flat_type", "max_price": "max_price", "town": "town"}
    asked = {e["field"] for e in pipeline if e.get("event") == "clarifying_question" and e.get("field")}
    result = dict(query_dict)
    for field, query_key in _field_to_query_key.items():
        if field in asked and query_key not in result:
            result[query_key] = None
    return result


# ── Public streaming pipeline ─────────────────────────────────────────────────

async def investigate_stream(
    repo: Repository,
    profile_text: str,
    limit: int = 5,
    model_override: str | None = None,
) -> AsyncGenerator[dict, None]:
    case = homeos_case_store.create_case(profile_text)
    case_id = case["case_id"]
    logger.info("[case:%s] START profile=%r", case_id[:8], profile_text[:80])

    try:
        # ── Phase 1: Profile ────────────────────────────────────────────────
        yield {"event": "agent_start", "agent": "profile", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_start", "agent": "profile", "block_id": None})
        if is_mock_mode():
            await asyncio.sleep(mock_delay_seconds())

        if is_mock_mode():
            avatar = mock_profile_avatar(profile_text, parse_homeos_profile(profile_text))
            tool_calls = []
        else:
            try:
                avatar, _, result = await _run_profile_agent(profile_text, model_override)
                tool_calls = _extract_tool_calls(result)
            except Exception as exc:
                logger.warning("[case:%s] profile model failed; using deterministic fallback: %s", case_id[:8], exc)
                avatar = mock_profile_avatar(profile_text, parse_homeos_profile(profile_text))
                tool_calls = []

        avatar_dict = _apply_rule_profile_fallback(avatar.model_dump(), profile_text)
        homeos_case_store.set_avatar(case_id, avatar_dict)
        prefs = avatar_dict.get("preferences", {})
        logger.info(
            "[case:%s] profile done  buyer_type=%s flat_type=%s max_price=%s",
            case_id[:8], avatar_dict.get("buyer_type"), prefs.get("flat_type"), prefs.get("max_price"),
        )

        if tool_calls:
            tool_evt = {"event": "tool_calls", "agent": "profile", "block_id": None, "tool_calls": tool_calls}
            yield tool_evt
            homeos_case_store.append_event(case_id, tool_evt)

        profile_summary = {
            "event": "agent_summary", "agent": "profile", "block_id": None,
            "narrative": avatar.summary, "data": avatar_dict,
        }
        yield profile_summary
        homeos_case_store.append_event(case_id, profile_summary)
        yield {"event": "agent_done", "agent": "profile", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_done", "agent": "profile", "block_id": None})

        # ── Phase 2: Search ─────────────────────────────────────────────────
        if not _is_estate_related_text(profile_text):
            homeos_case_store.set_status(case_id, "refining")
            q_evt = {
                "event": "clarifying_question",
                "case_id": case_id,
                "question": (
                    "Tell me what kind of Singapore property you're looking for, "
                    "including flat type, budget, town, commute, or school needs."
                ),
                "field": "profile_text",
            }
            yield q_evt
            homeos_case_store.append_event(case_id, q_evt)
            return

        yield {"event": "agent_start", "agent": "search", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_start", "agent": "search", "block_id": None})

        all_candidates, ranked, query_dict = await _search_phase(repo, case_id, prefs)
        candidate_ids = [c["block_id"] for c in all_candidates]
        homeos_case_store.set_search_state(case_id, prefs, candidate_ids)

        _current_pipeline = homeos_case_store.get_case(case_id).get("pipeline", [])
        search_evt = {
            "event": "agent_summary", "agent": "search", "block_id": None,
            "narrative": f"Found {len(all_candidates)} matching properties.",
            "data": {
                "candidates_found": len(all_candidates),
                "candidate_ids": candidate_ids[:200],
                "search_query": _add_skipped_fields(query_dict, _current_pipeline),
            },
        }
        yield search_evt
        homeos_case_store.append_event(case_id, search_evt)
        yield {"event": "agent_done", "agent": "search", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_done", "agent": "search", "block_id": None})

        # Only ask questions while the result set is still large. At or below
        # _ANALYSIS_THRESHOLD there is nothing to narrow, so go straight to
        # deep analysis (no clarifying questions, no preference review).
        if len(all_candidates) > _ANALYSIS_THRESHOLD:
            _current_pipeline = homeos_case_store.get_case(case_id).get("pipeline", [])
            question, field = _clarifying_question(prefs, len(all_candidates), _current_pipeline)
            if question is not None:
                logger.info(
                    "[case:%s] REFINING  count=%d  field=%s  question=%r",
                    case_id[:8], len(all_candidates), field, question[:60],
                )
                homeos_case_store.set_status(case_id, "refining")
                q_evt = {"event": "clarifying_question", "case_id": case_id, "question": question, "field": field}
                yield q_evt
                homeos_case_store.append_event(case_id, q_evt)
                return

            # Preference completeness review — only while the set is large.
            review_q, review_field = _preference_review(
                query_dict, prefs, len(all_candidates), _current_pipeline)
            if review_q is not None:
                logger.info("[case:%s] PREFERENCE REVIEW  count=%d", case_id[:8], len(all_candidates))
                homeos_case_store.set_status(case_id, "refining")
                q_evt = {"event": "clarifying_question", "case_id": case_id,
                         "question": review_q, "field": review_field}
                yield q_evt
                homeos_case_store.append_event(case_id, q_evt)
                return

            logger.info(
                "[case:%s] all constraints set, proceeding with top-%d from %d",
                case_id[:8], _ANALYSIS_THRESHOLD, len(all_candidates),
            )
            proceed_evt = {
                "event": "agent_summary", "agent": "search", "block_id": None,
                "narrative": (
                    f"No further constraints to apply — analysing the top {_ANALYSIS_THRESHOLD} "
                    f"from {len(all_candidates)} matching properties."
                ),
            }
            yield proceed_evt
            homeos_case_store.append_event(case_id, proceed_evt)

        # Small result set: confirm before analysing (user taps Proceed chip).
        if len(all_candidates) == 0:
            homeos_case_store.set_status(case_id, "refining")
            q_evt = {"event": "clarifying_question", "case_id": case_id,
                     "question": _no_candidates_question(), "field": "no_results"}
            yield q_evt
            homeos_case_store.append_event(case_id, q_evt)
            return

        if len(all_candidates) <= _ANALYSIS_THRESHOLD:
            homeos_case_store.set_status(case_id, "refining")
            q_evt = {"event": "clarifying_question", "case_id": case_id,
                     "question": _ready_to_proceed_question(len(all_candidates)),
                     "field": "ready_to_proceed"}
            yield q_evt
            homeos_case_store.append_event(case_id, q_evt)
            return

        # ── Phase 3: Deep analysis ──────────────────────────────────────────
        async for evt in _deep_analysis_stream(repo, case_id, ranked, prefs, model_override):
            yield evt

    except Exception as exc:
        logger.exception("[case:%s] ERROR %s", case_id[:8], exc)
        homeos_case_store.set_status(case_id, "error")
        error_evt = {"event": "case_error", "case_id": case_id, "message": str(exc)}
        yield error_evt
        homeos_case_store.append_event(case_id, error_evt)


async def refine_stream(
    repo: Repository,
    case_id: str,
    user_message: str,
    model_override: str | None = None,
) -> AsyncGenerator[dict, None]:
    case = homeos_case_store.get_case(case_id)
    if case is None:
        yield {"event": "case_error", "case_id": case_id, "message": "Case not found."}
        return
    if case["status"] not in ("refining",):
        yield {"event": "case_error", "case_id": case_id, "message": "Case is not awaiting refinement."}
        return

    homeos_case_store.set_status(case_id, "running")
    homeos_case_store.append_message(case_id, "user", user_message)
    logger.info("[case:%s] REFINE  message=%r", case_id[:8], user_message[:80])

    try:
        # "proceed" (and friends) means: stop asking, analyse what we have now.
        force_proceed = _is_proceed_intent(user_message)
        if force_proceed:
            logger.info("[case:%s] PROCEED intent — analysing current candidates", case_id[:8])
            prefs = {k: v for k, v in case.get("search_prefs", {}).items() if v is not None}
        else:
            refinement_prompt = _build_refinement_prompt(case)
            logger.info("[case:%s] refinement prompt:\n%s", case_id[:8], refinement_prompt)

            if is_mock_mode():
                avatar = mock_profile_avatar(refinement_prompt, parse_homeos_profile(refinement_prompt))
            else:
                try:
                    avatar, _, _ = await _run_profile_agent(refinement_prompt, model_override)
                except Exception as exc:
                    logger.warning("[case:%s] refinement model failed; using deterministic fallback: %s", case_id[:8], exc)
                    avatar = mock_profile_avatar(refinement_prompt, parse_homeos_profile(refinement_prompt))

            avatar_dict = _apply_rule_profile_fallback(avatar.model_dump(), refinement_prompt)
            prefs_from_ai = {k: v for k, v in avatar_dict.get("preferences", {}).items() if v is not None}

            base_prefs = {k: v for k, v in case.get("search_prefs", {}).items() if v is not None}
            overrides = _direct_answer_overrides(user_message, case["pipeline"])
            if overrides:
                logger.info("[case:%s] direct overrides applied: %s", case_id[:8], overrides)
            prefs = {**prefs_from_ai, **base_prefs, **overrides}

            avatar_dict["preferences"] = prefs
            homeos_case_store.set_avatar(case_id, avatar_dict)
        logger.info(
            "[case:%s] refined prefs  flat_type=%s max_price=%s commute=%s school=%s town=%s",
            case_id[:8], prefs.get("flat_type"), prefs.get("max_price"),
            prefs.get("commute_priority"), prefs.get("school_priority"), prefs.get("town"),
        )

        yield {"event": "agent_start", "agent": "search", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_start", "agent": "search", "block_id": None})

        all_candidates, ranked, query_dict = await _search_phase(repo, case_id, prefs)
        candidate_ids = [c["block_id"] for c in all_candidates]
        homeos_case_store.set_search_state(case_id, prefs, candidate_ids)

        search_evt = {
            "event": "agent_summary", "agent": "search", "block_id": None,
            "narrative": f"Refined search: {len(all_candidates)} matching properties.",
            "data": {
                "candidates_found": len(all_candidates),
                "candidate_ids": candidate_ids[:200],
                "search_query": _add_skipped_fields(query_dict, case["pipeline"]),
            },
        }
        yield search_evt
        homeos_case_store.append_event(case_id, search_evt)
        yield {"event": "agent_done", "agent": "search", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_done", "agent": "search", "block_id": None})

        # Skip all questioning when the user asked to proceed, or once the
        # result set is small enough that there is nothing left to narrow.
        if not force_proceed and len(all_candidates) > _ANALYSIS_THRESHOLD:
            question, field = _clarifying_question(prefs, len(all_candidates), case["pipeline"])
            if question is not None:
                logger.info("[case:%s] STILL REFINING  count=%d  field=%s", case_id[:8], len(all_candidates), field)
                homeos_case_store.set_status(case_id, "refining")
                q_evt = {"event": "clarifying_question", "case_id": case_id, "question": question, "field": field}
                yield q_evt
                homeos_case_store.append_event(case_id, q_evt)
                return

            # Preference completeness review — only while the set is large.
            _current_pipeline = homeos_case_store.get_case(case_id).get("pipeline", [])
            review_q, review_field = _preference_review(
                query_dict, prefs, len(all_candidates), _current_pipeline)
            if review_q is not None:
                logger.info("[case:%s] PREFERENCE REVIEW  count=%d", case_id[:8], len(all_candidates))
                homeos_case_store.set_status(case_id, "refining")
                q_evt = {"event": "clarifying_question", "case_id": case_id,
                         "question": review_q, "field": review_field}
                yield q_evt
                homeos_case_store.append_event(case_id, q_evt)
                return

            logger.info(
                "[case:%s] all constraints set, proceeding with top-%d from %d",
                case_id[:8], _ANALYSIS_THRESHOLD, len(all_candidates),
            )
            proceed_evt = {
                "event": "agent_summary", "agent": "search", "block_id": None,
                "narrative": (
                    f"No further constraints to apply — analysing the top {_ANALYSIS_THRESHOLD} "
                    f"from {len(all_candidates)} matching properties."
                ),
            }
            yield proceed_evt
            homeos_case_store.append_event(case_id, proceed_evt)

        # Small result set: confirm before analysing (user taps Proceed chip),
        # unless they already asked to proceed.
        if not force_proceed and len(all_candidates) == 0:
            homeos_case_store.set_status(case_id, "refining")
            q_evt = {"event": "clarifying_question", "case_id": case_id,
                     "question": _no_candidates_question(), "field": "no_results"}
            yield q_evt
            homeos_case_store.append_event(case_id, q_evt)
            return

        if not force_proceed and len(all_candidates) <= _ANALYSIS_THRESHOLD:
            homeos_case_store.set_status(case_id, "refining")
            q_evt = {"event": "clarifying_question", "case_id": case_id,
                     "question": _ready_to_proceed_question(len(all_candidates)),
                     "field": "ready_to_proceed"}
            yield q_evt
            homeos_case_store.append_event(case_id, q_evt)
            return

        async for evt in _deep_analysis_stream(repo, case_id, ranked, prefs, model_override):
            yield evt

    except Exception as exc:
        logger.exception("[case:%s] REFINE ERROR %s", case_id[:8], exc)
        homeos_case_store.set_status(case_id, "error")
        error_evt = {"event": "case_error", "case_id": case_id, "message": str(exc)}
        yield error_evt
        homeos_case_store.append_event(case_id, error_evt)


async def chat_in_case(
    case_id: str,
    message: str,
    model_override: str | None = None,
) -> AsyncGenerator[str, None]:
    from pydantic_ai import Agent
    from app.homeos.framework.registry import get_model

    case = homeos_case_store.get_case(case_id)
    if case is None:
        yield "Case not found."
        return

    homeos_case_store.append_message(case_id, "user", message)

    if not _is_estate_related_text(message):
        answer = (
            "I can only help with Singapore property decisions here: HDB, BTO, "
            "resale/private homes, locations, budgets, commute, schools, risks, "
            "listings, and viewing questions."
        )
        homeos_case_store.append_message(case_id, "assistant", answer)
        yield answer
        return

    if is_mock_mode():
        answer = mock_chat_answer(case, message)
        homeos_case_store.append_message(case_id, "assistant", answer)
        yield answer
        return

    pipeline_summary = json.dumps([
        {"event": e["event"], "agent": e.get("agent"), "narrative": e.get("narrative", "")}
        for e in case["pipeline"]
        if e["event"] in ("agent_summary", "case_done")
    ], indent=2)

    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in case["conversation"][:-1]
    )

    system = (
        "You are HomeOS, an HDB buyer agent. Answer using only the evidence below. "
        "Be direct, cite specific numbers where available. Max 150 words."
    )
    user_prompt = (
        f"Case evidence (agent pipeline summaries):\n{pipeline_summary}\n\n"
        f"{'Previous conversation:' + chr(10) + conversation_text + chr(10) + chr(10) if conversation_text else ''}"
        f"Question: {message}"
    )

    chat_agent: Agent[None, str] = Agent(get_model(model_override), output_type=str, system_prompt=system)
    result = await chat_agent.run(user_prompt)
    answer = result.output or "I need more information to answer that question."

    homeos_case_store.append_message(case_id, "assistant", answer)
    yield answer


# ── Sync helpers (used by non-streaming API routes) ───────────────────────────

def build_homeos_case_file(repo: Repository, profile_text: str, block_id: int) -> dict[str, Any]:
    from app.homeos.sync_agents import (
        lifestyle_analysis_agent,
        location_graph_agent,
        market_analysis_agent,
        risk_value_agent,
        viewing_questions_agent,
    )

    block = repo.block(block_id)
    if block is None:
        raise ValueError("block not found")

    avatar = parse_homeos_profile(profile_text)
    prefs = avatar["preferences"]
    market = market_analysis_agent(repo, block_id, prefs)
    location = location_graph_agent(repo, block_id)
    risk = risk_value_agent(repo, block_id, prefs)
    provider, destinations = _build_lifestyle_inputs(repo, prefs)
    lifestyle = lifestyle_analysis_agent(repo, block_id, provider, destinations)
    score, reasons, watchouts = worth_viewing_score(market, location, risk, prefs, lifestyle)
    questions = viewing_questions_agent({"market": market, "location": location, "risk": risk})

    return {
        "block_id": block_id,
        "block_number": block.block_number,
        "street_name": block.street_name,
        "town": block.town,
        "verdict": _verdict(score),
        "worth_viewing_score": score,
        "confidence": _confidence(market["transaction_count"]),
        "top_reasons": reasons,
        "top_watchouts": watchouts,
        "evidence": {
            "recent_sales": market,
            "connections": location["connections"],
            "risks": item_texts(watchouts),
            "future_signals": {
                "future_mrt": risk["future_mrt"],
                "future_supply": risk["future_supply"],
            },
            "lifestyle": lifestyle,
            "agent_questions": questions,
        },
        "trace": [],
    }


def investigate_homeos_profile(
    repo: Repository, profile_text: str, limit: int = 5
) -> dict[str, Any]:
    avatar = parse_homeos_profile(profile_text)
    if is_mock_mode():
        avatar = mock_profile_avatar(profile_text, avatar).model_dump()
    rows = []
    for block in repo.blocks():
        try:
            case_file = build_homeos_case_file(repo, profile_text, block.block_id)
        except Exception:
            continue
        if (
            avatar["preferences"]["flat_type"]
            and case_file["evidence"]["recent_sales"]["transaction_count"] == 0
        ):
            continue
        rows.append({
            "block_id": case_file["block_id"],
            "block_number": case_file["block_number"],
            "street_name": case_file["street_name"],
            "town": case_file["town"],
            "worth_viewing_score": case_file["worth_viewing_score"],
            "verdict": case_file["verdict"],
            "confidence": case_file["confidence"],
            "top_reasons": case_file["top_reasons"],
            "top_watchouts": case_file["top_watchouts"],
        })
    rows.sort(key=lambda r: (-r["worth_viewing_score"], r["block_id"]))
    return {"avatar": avatar, "shortlist": rows[:limit]}


def schedule_homeos_viewing(
    repo: Repository,
    profile_text: str,
    block_id: int,
    availability: list[str],
    contact_name: str,
    contact_note: str | None = None,
) -> dict[str, Any]:
    block = repo.block(block_id)
    if block is None:
        raise ValueError("block not found")
    clean_availability = [s.strip() for s in availability if s.strip()]
    if not clean_availability:
        raise ValueError("at least one availability slot is required")

    avatar = parse_homeos_profile(profile_text)
    case_file = build_homeos_case_file(repo, profile_text, block_id)
    address = f"Blk {block.block_number} {block.street_name}"
    availability_text = "; ".join(clean_availability)
    question_text = " ".join(case_file["evidence"]["agent_questions"][:2])
    note = f" Note: {contact_note.strip()}" if contact_note and contact_note.strip() else ""
    message = (
        f"Hi, {contact_name.strip()} would like to view {address}. "
        f"Availability: {availability_text}. "
        f"Buyer profile: {avatar['summary']} "
        f"Due-diligence questions: {question_text}{note}"
    )
    count = len(clean_availability)
    return {
        "status": "ready_for_agent",
        "confirmation": (
            f"{address} is selected for viewing. HomeOS prepared the scheduling handoff with "
            f"{count} availability window{'s' if count != 1 else ''}."
        ),
        "outbox": {
            "block_id": block_id,
            "recipient_type": "real_estate_agent",
            "message": message,
            "availability": clean_availability,
        },
    }
