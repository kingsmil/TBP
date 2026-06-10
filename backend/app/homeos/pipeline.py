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
    for flat_type in FLAT_TYPES:
        if flat_type in norm:
            return flat_type
    if "2ROOM" in compact:
        return "2 ROOM"
    if "3ROOM" in compact:
        return "3 ROOM"
    if "4ROOM" in compact:
        return "4 ROOM"
    if "5ROOM" in compact:
        return "5 ROOM"
    if "EXEC" in compact:
        return "EXECUTIVE"
    return None


def _extract_budget(text: str) -> float | None:
    lowered = text.lower().replace(",", "")
    patterns = [
        r"(?:under|below|up to|max|maximum|budget)\s*\$?\s*(\d+(?:\.\d+)?)\s*(m|mil|million|k)?",
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
    return None


def _extract_work_locations(text: str) -> list[str]:
    locations: list[str] = []
    pattern = re.compile(
        r"\b(?:work|works|working|office)\s+(?:at|in|near)\s+"
        r"([A-Za-z][A-Za-z0-9 .'-]*?)(?=\s+(?:and|with|but|because|while|plus)\b|[.,;]|$)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        loc = " ".join(match.group(1).split()).strip(" .,-")
        if loc and loc.casefold() not in {x.casefold() for x in locations}:
            locations.append(loc)
    return locations


def parse_homeos_profile(profile_text: str) -> dict[str, Any]:
    buyer_type = "family" if _has_any(profile_text, ("family", "kids", "children", "child", "primary school", "schools")) else "single"
    if _has_any(profile_text, ("must be close to mrt", "near mrt", "close to mrt", "commute", "mrt access", "within 600")):
        commute_priority = "high"
    elif _has_any(profile_text, ("medium commute", "1.2km", "1200", "moderate commute", "within 1.2", "within 1km of mrt",
                                  "works in", "work in", "office in", "workplace", "cbd", "raffles place", "tanjong pagar",
                                  "city hall", "marina bay", "one north", "jurong east")):
        commute_priority = "medium"
    else:
        commute_priority = "low"
    school_priority = "high" if _has_any(profile_text, ("primary school", "schools", "kids", "children", "family")) else "low"
    risk_tolerance = "medium" if _has_any(profile_text, ("some risk", "appreciation risk", "growth", "invest")) else "low"
    appreciation_priority = "high" if _has_any(profile_text, ("growth", "appreciation", "investment", "undervalued")) else "medium"
    work_locations = _extract_work_locations(profile_text)
    bus_reliance = "high" if _has_any(
        profile_text,
        ("no car", "without a car", "don't drive", "doesn't drive", "depend on bus", "depends on bus",
         "depend on buses", "depends on buses", "rely on bus", "rely on buses", "bus dependent"),
    ) else "low"
    if buyer_type == "family":
        label = "Family HomeOS Agent"
        summary = "Family buyer prioritizing schools, budget fit, and lower-risk viewing choices."
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
            "commute_priority": commute_priority,
            "school_priority": school_priority,
            "risk_tolerance": risk_tolerance,
            "appreciation_priority": appreciation_priority,
            "work_locations": work_locations,
            "bus_reliance": bus_reliance,
        },
    }


# ── Registry-backed agent runner ──────────────────────────────────────────────

async def _run_profile_agent(prompt: str):
    """Run the profile agent via the tool repository. Returns (HomeOSAvatar, {}, result)."""
    from app.homeos.wiring import tool_repository
    agent, prefetched = tool_repository.build_agent("profile", repo=None, block_id=None, prefs={})
    result = await agent.run(prompt)
    return result.output, prefetched, result


async def _run_block_agent(name: str, repo: Repository, block_id: int, prefs: dict, prompt: str):
    """Run a named block-level agent. Returns (output_model, prefetched_dict, result)."""
    from app.homeos.wiring import tool_repository
    agent, prefetched = tool_repository.build_agent(name, repo=repo, block_id=block_id, prefs=prefs)
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


# ── Deep analysis ─────────────────────────────────────────────────────────────

async def _deep_analysis_stream(
    repo: Repository,
    case_id: str,
    candidates: list[dict],
    prefs: dict,
) -> AsyncGenerator[dict, None]:
    """Phase 3: run market/location/risk agents on each candidate via registry."""
    rows = []
    for candidate in candidates:
        block_id = candidate["block_id"]
        market_evidence: dict = {}
        location_evidence: dict = {}
        risk_evidence: dict = {}

        try:
            mock = is_mock_mode()

            # ── Market ────────────────────────────────────────────────────────
            start_evt = {"event": "agent_start", "agent": "market", "block_id": block_id}
            yield start_evt
            homeos_case_store.append_event(case_id, start_evt)
            if mock:
                await asyncio.sleep(mock_delay_seconds())

            from app.homeos.wiring import tool_repository
            if mock:
                # In mock mode, prefetch data and use mock narrative
                _, prefetched_market = tool_repository.build_agent("market", repo=repo, block_id=block_id, prefs=prefs)
                txn_data = prefetched_market.get("transactions", {})
                market_narrative = mock_market_narrative(txn_data, prefs)
                market_evidence = {**txn_data, "narrative": market_narrative}
            else:
                # In AI mode, let agent call tools and return complete evidence
                output, _, result = await _run_block_agent(
                    "market", repo, block_id, prefs,
                    "Analyze market evidence for this block using the available tools.",
                )
                market_evidence = output.model_dump()
                tool_calls = _extract_tool_calls(result)
                if tool_calls:
                    tool_evt = {"event": "tool_calls", "agent": "market", "block_id": block_id, "tool_calls": tool_calls}
                    yield tool_evt
                    homeos_case_store.append_event(case_id, tool_evt)

            yield {"event": "agent_data", "agent": "market", "block_id": block_id, "data": market_evidence}
            homeos_case_store.append_event(case_id, {"event": "agent_data", "agent": "market", "block_id": block_id, "data": market_evidence})
            yield {"event": "agent_summary", "agent": "market", "block_id": block_id, "narrative": market_evidence.get("narrative", "")}
            homeos_case_store.append_event(case_id, {"event": "agent_summary", "agent": "market", "block_id": block_id, "narrative": market_evidence.get("narrative", "")})
            yield {"event": "agent_done", "agent": "market", "block_id": block_id}
            homeos_case_store.append_event(case_id, {"event": "agent_done", "agent": "market", "block_id": block_id})

            # ── Location ──────────────────────────────────────────────────────
            start_evt = {"event": "agent_start", "agent": "location", "block_id": block_id}
            yield start_evt
            homeos_case_store.append_event(case_id, start_evt)
            if mock:
                await asyncio.sleep(mock_delay_seconds())

            if mock:
                # In mock mode, prefetch data and use mock narrative
                _, prefetched_loc = tool_repository.build_agent("location", repo=repo, block_id=block_id, prefs=prefs)
                prox_data = prefetched_loc.get("proximity", {})
                connections = prox_data.get("connections", [])
                location_narrative = mock_location_narrative(connections)
                location_evidence = {**prox_data, "narrative": location_narrative}
            else:
                # In AI mode, let agent call tools and return complete evidence
                output, _, result = await _run_block_agent(
                    "location", repo, block_id, prefs,
                    "Analyze location and connectivity for this block using the available tools.",
                )
                location_evidence = output.model_dump()
                tool_calls = _extract_tool_calls(result)
                if tool_calls:
                    tool_evt = {"event": "tool_calls", "agent": "location", "block_id": block_id, "tool_calls": tool_calls}
                    yield tool_evt
                    homeos_case_store.append_event(case_id, tool_evt)

            yield {"event": "agent_data", "agent": "location", "block_id": block_id, "data": location_evidence}
            homeos_case_store.append_event(case_id, {"event": "agent_data", "agent": "location", "block_id": block_id, "data": location_evidence})
            yield {"event": "agent_summary", "agent": "location", "block_id": block_id, "narrative": location_evidence.get("narrative", "")}
            homeos_case_store.append_event(case_id, {"event": "agent_summary", "agent": "location", "block_id": block_id, "narrative": location_evidence.get("narrative", "")})
            yield {"event": "agent_done", "agent": "location", "block_id": block_id}
            homeos_case_store.append_event(case_id, {"event": "agent_done", "agent": "location", "block_id": block_id})

            # ── Risk ──────────────────────────────────────────────────────────
            start_evt = {"event": "agent_start", "agent": "risk", "block_id": block_id}
            yield start_evt
            homeos_case_store.append_event(case_id, start_evt)
            if mock:
                await asyncio.sleep(mock_delay_seconds())

            if mock:
                # In mock mode, prefetch data and compute manually
                _, prefetched_risk = tool_repository.build_agent("risk", repo=repo, block_id=block_id, prefs=prefs)
                app_data = prefetched_risk.get("appreciation", {})
                future_dev_data = prefetched_risk.get("future_dev", {})
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
                risk_narrative = mock_risk_narrative({
                    "watchouts": watchouts,
                    "score_adjustment": score_adjustment,
                })
                risk_evidence = {
                    "appreciation": app_data,
                    "future_mrt": future_dev_data.get("future_mrt"),
                    "future_supply": future_supply_data,
                    "watchouts": watchouts,
                    "score_adjustment": score_adjustment,
                    "narrative": risk_narrative,
                }
            else:
                # In AI mode, let agent call tools, compute watchouts and score_adjustment
                output, _, result = await _run_block_agent(
                    "risk", repo, block_id, prefs,
                    f"Analyze risk factors for this block. Buyer risk_tolerance: {prefs.get('risk_tolerance', 'low')}",
                )
                risk_evidence = output.model_dump()
                tool_calls = _extract_tool_calls(result)
                if tool_calls:
                    tool_evt = {"event": "tool_calls", "agent": "risk", "block_id": block_id, "tool_calls": tool_calls}
                    yield tool_evt
                    homeos_case_store.append_event(case_id, tool_evt)

            yield {"event": "agent_data", "agent": "risk", "block_id": block_id, "data": risk_evidence}
            homeos_case_store.append_event(case_id, {"event": "agent_data", "agent": "risk", "block_id": block_id, "data": risk_evidence})
            yield {"event": "agent_summary", "agent": "risk", "block_id": block_id, "narrative": risk_evidence.get("narrative", "")}
            homeos_case_store.append_event(case_id, {"event": "agent_summary", "agent": "risk", "block_id": block_id, "narrative": risk_evidence.get("narrative", "")})
            yield {"event": "agent_done", "agent": "risk", "block_id": block_id}
            homeos_case_store.append_event(case_id, {"event": "agent_done", "agent": "risk", "block_id": block_id})

        except Exception as exc:
            logger.warning("[case:%s] agent error for block %d: %s — skipping", case_id[:8], block_id, exc)
            continue

        txn_count = market_evidence.get("transaction_count", 0)
        score, reasons, watchouts = worth_viewing_score(market_evidence, location_evidence, risk_evidence, prefs)
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
        })

    rows.sort(key=lambda r: (-r["worth_viewing_score"], r["block_id"]))
    homeos_case_store.set_shortlist(case_id, rows)
    homeos_case_store.set_status(case_id, "done")
    logger.info("[case:%s] DONE  shortlist=%d", case_id[:8], len(rows))

    done_evt = {"event": "case_done", "case_id": case_id, "shortlist": rows}
    yield done_evt
    homeos_case_store.append_event(case_id, done_evt)


# ── Search phase helpers ───────────────────────────────────────────────────────

def _prefs_to_search_query(prefs: dict, candidate_limit: int = 100):
    from app.core.models import SearchQuery
    school = prefs.get("school_priority", "low")
    min_schools = prefs.get("min_schools_within_1km")
    if min_schools is None:
        if school == "high":
            min_schools = 2
        elif school == "medium":
            min_schools = 1
    # Only hard-filter by MRT when the buyer explicitly stated a preference.
    # "low" is the implicit default — zero filter applied when commute was never mentioned.
    commute = prefs.get("commute_priority", "low")
    if commute == "high":
        max_mrt_distance_m = 600.0
    elif commute == "medium":
        max_mrt_distance_m = 1200.0
    else:
        max_mrt_distance_m = None
    return SearchQuery(
        flat_type=prefs.get("flat_type"),
        max_price=prefs.get("max_price"),
        town=prefs.get("town"),
        max_mrt_distance_m=max_mrt_distance_m,
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


_ANALYSIS_THRESHOLD = 10
_SOFT_THRESHOLD = 30


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

        q_text = dim.question or dim.prompt
        preamble = f"I've narrowed it to {count} blocks." if count <= 10 else f"Still {count} options."
        return (f"{preamble} {q_text}", dim.field)

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
    if "flat type" in lower_q or "room" in lower_q:
        ft = _extract_flat_type(user_message)
        if ft:
            updates["flat_type"] = ft
    elif "budget" in lower_q or "maximum" in lower_q:
        budget = _extract_budget(user_message)
        if budget:
            updates["max_price"] = budget
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
        # Extract town name from natural language using fuzzy matching
        from app.core.models import HDBTown
        from app.homeos.tools.search import _fuzzy_match_town

        # Try to find any HDB town mentioned in the message
        words = user_message.upper().split()
        town_enum = None

        # Check each word and phrase for a town match
        for i in range(len(words)):
            for length in range(1, min(4, len(words) - i + 1)):  # Try 1-3 word phrases
                phrase = " ".join(words[i:i+length])
                matched = _fuzzy_match_town(phrase)
                if matched:
                    town_enum = matched
                    break
            if town_enum:
                break

        if town_enum:
            updates["town"] = town_enum.value
    return updates


async def _search_phase(
    repo: Repository,
    case_id: str,
    prefs: dict,
) -> tuple[list[dict], list[dict], dict]:
    from app.services.search import search_blocks
    import dataclasses
    search_q = _prefs_to_search_query(prefs, candidate_limit=500)
    query_dict = {k: v for k, v in dataclasses.asdict(search_q).items() if v is not None and k != "limit"}
    candidates = await asyncio.to_thread(search_blocks, repo, search_q)
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
            avatar, _, result = await _run_profile_agent(profile_text)
            tool_calls = _extract_tool_calls(result)

        avatar_dict = avatar.model_dump()
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

        # ── Phase 2b: Preference completeness review (one round per case) ────
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

        # ── Phase 3: Deep analysis ──────────────────────────────────────────
        async for evt in _deep_analysis_stream(repo, case_id, ranked, prefs):
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
        refinement_prompt = _build_refinement_prompt(case)
        logger.info("[case:%s] refinement prompt:\n%s", case_id[:8], refinement_prompt)

        if is_mock_mode():
            avatar = mock_profile_avatar(refinement_prompt, parse_homeos_profile(refinement_prompt))
        else:
            avatar, _, _ = await _run_profile_agent(refinement_prompt)

        avatar_dict = avatar.model_dump()
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

        if len(all_candidates) > _ANALYSIS_THRESHOLD:
            question, field = _clarifying_question(prefs, len(all_candidates), case["pipeline"])
            if question is not None:
                logger.info("[case:%s] STILL REFINING  count=%d  field=%s", case_id[:8], len(all_candidates), field)
                homeos_case_store.set_status(case_id, "refining")
                q_evt = {"event": "clarifying_question", "case_id": case_id, "question": question, "field": field}
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

        # ── Preference completeness review (one round per case) ──────────────
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

        async for evt in _deep_analysis_stream(repo, case_id, ranked, prefs):
            yield evt

    except Exception as exc:
        logger.exception("[case:%s] REFINE ERROR %s", case_id[:8], exc)
        homeos_case_store.set_status(case_id, "error")
        error_evt = {"event": "case_error", "case_id": case_id, "message": str(exc)}
        yield error_evt
        homeos_case_store.append_event(case_id, error_evt)


async def chat_in_case(case_id: str, message: str) -> AsyncGenerator[str, None]:
    from pydantic_ai import Agent
    from app.homeos.framework.registry import get_model

    case = homeos_case_store.get_case(case_id)
    if case is None:
        yield "Case not found."
        return

    homeos_case_store.append_message(case_id, "user", message)

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

    chat_agent: Agent[None, str] = Agent(get_model(), output_type=str, system_prompt=system)
    result = await chat_agent.run(user_prompt)
    answer = result.output or "I need more information to answer that question."

    homeos_case_store.append_message(case_id, "assistant", answer)
    yield answer


# ── Sync helpers (used by non-streaming API routes) ───────────────────────────

def build_homeos_case_file(repo: Repository, profile_text: str, block_id: int) -> dict[str, Any]:
    from app.homeos.sync_agents import (
        location_graph_agent,
        market_analysis_agent,
        risk_value_agent,
        viewing_questions_agent,
    )

    block = repo.block(block_id)
    if block is None:
        raise ValueError("block not found")

    avatar = parse_homeos_profile(profile_text)
    market = market_analysis_agent(repo, block_id, avatar["preferences"])
    location = location_graph_agent(repo, block_id)
    risk = risk_value_agent(repo, block_id, avatar["preferences"])
    score, reasons, watchouts = worth_viewing_score(market, location, risk, avatar["preferences"])
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
