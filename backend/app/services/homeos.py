"""HomeOS Agent: profile parsing, HDB investigation, and viewing handoff."""
from __future__ import annotations

import dataclasses
import logging
import re
from typing import Any

logger = logging.getLogger("homeos.pipeline")


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


from app.repositories.base import Repository


def parse_homeos_profile(profile_text: str) -> dict[str, Any]:
    """Parse natural-language household goals into HomeOS buyer preferences."""
    buyer_type = "family" if _has_any(profile_text, ("family", "kids", "children", "child", "primary school", "schools")) else "single"
    commute_priority = "high" if _has_any(profile_text, ("must be close to mrt", "near mrt", "close to mrt", "commute")) else "medium"
    school_priority = "high" if _has_any(profile_text, ("primary school", "schools", "kids", "children", "family")) else "low"
    risk_tolerance = "medium" if _has_any(profile_text, ("some risk", "appreciation risk", "growth", "invest")) else "low"
    appreciation_priority = "high" if _has_any(profile_text, ("growth", "appreciation", "investment", "undervalued")) else "medium"

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
        },
    }


def _verdict(score: float) -> str:
    if score >= 75:
        return "Worth viewing"
    if score >= 50:
        return "Maybe view"
    return "Skip for now"


def _confidence(txn_count: int) -> str:
    if txn_count >= 6:
        return "high"
    if txn_count >= 3:
        return "medium"
    return "low"


def build_homeos_case_file(repo: Repository, profile_text: str, block_id: int) -> dict[str, Any]:
    from app.services.homeos_agents import (
        location_graph_agent,
        market_analysis_agent,
        risk_value_agent,
        viewing_questions_agent,
        worth_viewing_score,
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
            "risks": watchouts,
            "future_signals": {
                "future_mrt": risk["future_mrt"],
                "future_supply": risk["future_supply"],
            },
            "agent_questions": questions,
        },
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


import asyncio
import json
from collections.abc import AsyncGenerator

from app.services import homeos_case_store
from app.services.homeos_ai_agents import get_model, profile_agent
from app.services.homeos_mock_agents import (
    is_mock_mode,
    mock_chat_answer,
    mock_delay_seconds,
    mock_profile_avatar,
)


def _prefs_to_search_query(prefs: dict, candidate_limit: int = 100) -> "SearchQuery":
    """Convert HomeOSPreferences dict into a SearchQuery for the search_blocks call."""
    from app.core.models import SearchQuery

    commute = prefs.get("commute_priority", "medium")
    school = prefs.get("school_priority", "low")

    max_mrt = None
    if commute == "high":
        max_mrt = 600.0
    elif commute == "medium":
        max_mrt = 1200.0

    # Explicit count beats priority label
    min_schools = prefs.get("min_schools_within_1km")
    if min_schools is None:
        if school == "high":
            min_schools = 2
        elif school == "medium":
            min_schools = 1

    return SearchQuery(
        flat_type=prefs.get("flat_type"),
        max_price=prefs.get("max_price"),
        town=prefs.get("town"),
        max_mrt_distance_m=max_mrt,
        min_schools_within_1km=min_schools,
        limit=candidate_limit,
    )


def _lightweight_rank(candidates: list[dict], prefs: dict, top_n: int) -> list[dict]:
    """
    Score and rank search results using only the fields already returned by
    /properties/search — no extra DB queries or LLM calls needed.
    Picks the top_n candidates to pass to the expensive deep-analysis agents.
    """
    commute = prefs.get("commute_priority", "medium")
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

    ranked = sorted(candidates, key=_score, reverse=True)
    return ranked[:top_n]


_ANALYSIS_THRESHOLD = 10  # run deep agents only when candidates ≤ this


def _clarifying_question(prefs: dict, count: int) -> tuple[str, str]:
    """Rule-based: pick the most impactful missing constraint.
    Returns (question_text, field_name) so callers can store context for parsing the answer."""
    if not prefs.get("flat_type"):
        return (
            f"I found {count} matching properties. "
            "What type of flat are you looking for — 2-room, 3-room, 4-room, 5-room, or Executive?",
            "flat_type",
        )
    if not prefs.get("max_price"):
        return (
            f"I found {count} {prefs['flat_type']} flats. "
            "What's your maximum budget? (e.g. $600k, $700k, $800k, $1M)",
            "max_price",
        )
    if prefs.get("commute_priority", "medium") != "high":
        return (
            f"Still {count} options. How important is being close to an MRT? "
            "High = within 600 m, Medium = within 1.2 km.",
            "commute_priority",
        )
    if prefs.get("school_priority", "low") == "low":
        return (
            f"Still {count} options. Do you need primary schools nearby? "
            "High = 2+ within 1 km, Medium = 1+ within 1 km.",
            "school_priority",
        )
    return (
        f"Still {count} options — quite a lot! "
        "Could you name a preferred town or estate? (e.g. Tampines, Bishan, Toa Payoh, Jurong East)",
        "town",
    )


def _build_refinement_prompt(case: dict) -> str:
    """Build a structured Q&A prompt so the profile agent has explicit context for every answer.

    Pairs each clarifying_question event from the pipeline with the matching
    user conversation message. The new message must already be appended to
    case["conversation"] before this function is called.
    """
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
    """Rule-based extraction for the field the last clarifying question was asking about.

    The LLM cannot reliably map short answers like 'within 600m' or 'high please'
    back to enum values without knowing the question context. This function looks at
    the last clarifying_question event in the pipeline (immutable history — no stored
    state needed), identifies the field being asked, and directly parses the user's
    answer. The result is merged over the LLM's prefs as a guaranteed override.
    """
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
        # Match both enum labels ("high") and distance answers ("within 600m", "600m")
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
        town_candidate = user_message.upper().strip()
        for filler in ("I PREFER ", "PREFER ", "MAYBE ", "PERHAPS ", "IN ", "AROUND ", "NEAR "):
            town_candidate = town_candidate.replace(filler, "").strip()
        if town_candidate:
            updates["town"] = town_candidate

    return updates


async def _deep_analysis_stream(
    repo: Repository,
    case_id: str,
    candidates: list[dict],
    prefs: dict,
) -> AsyncGenerator[dict, None]:
    """Phase 3: run market/location/risk agents on each candidate, yield all events."""
    from app.services.homeos_agents import (
        location_graph_agent,
        market_analysis_agent,
        risk_value_agent,
        worth_viewing_score,
    )

    rows = []
    for candidate in candidates:
        block_id = candidate["block_id"]
        market_evidence: dict = {}
        location_evidence: dict = {}
        risk_evidence: dict = {}

        for agent_name, agent_fn, agent_args in [
            ("market",   market_analysis_agent, (repo, block_id, prefs)),
            ("location", location_graph_agent,  (repo, block_id)),
            ("risk",     risk_value_agent,       (repo, block_id, prefs)),
        ]:
            start_evt = {"event": "agent_start", "agent": agent_name, "block_id": block_id}
            yield start_evt
            homeos_case_store.append_event(case_id, start_evt)
            if is_mock_mode():
                await asyncio.sleep(mock_delay_seconds())

            evidence = await asyncio.to_thread(agent_fn, *agent_args)

            data_evt = {"event": "agent_data", "agent": agent_name, "block_id": block_id, "data": evidence}
            yield data_evt
            homeos_case_store.append_event(case_id, data_evt)

            narrative = evidence.get("narrative", "")
            summary_evt = {"event": "agent_summary", "agent": agent_name, "block_id": block_id, "narrative": narrative}
            yield summary_evt
            homeos_case_store.append_event(case_id, summary_evt)

            done_evt = {"event": "agent_done", "agent": agent_name, "block_id": block_id}
            yield done_evt
            homeos_case_store.append_event(case_id, done_evt)

            if agent_name == "market":
                market_evidence = evidence
            elif agent_name == "location":
                location_evidence = evidence
            elif agent_name == "risk":
                risk_evidence = evidence

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


async def _search_phase(
    repo: Repository,
    case_id: str,
    prefs: dict,
) -> tuple[list[dict], list[dict], dict]:
    """Run search_blocks and lightweight-rank. Returns (all_candidates, top_ranked, query_dict)."""
    from app.services.search import search_blocks

    search_q = _prefs_to_search_query(prefs, candidate_limit=500)
    query_dict = {k: v for k, v in dataclasses.asdict(search_q).items() if v is not None and k != "limit"}
    candidates = await asyncio.to_thread(search_blocks, repo, search_q)
    logger.info(
        "[case:%s] search returned %d candidates  query=%s",
        case_id[:8], len(candidates), query_dict,
    )
    ranked = _lightweight_rank(candidates, prefs, top_n=_ANALYSIS_THRESHOLD)
    return candidates, ranked, query_dict


async def investigate_stream(
    repo: Repository,
    profile_text: str,
    limit: int = 5,
) -> AsyncGenerator[dict, None]:
    """
    Conversational investigation pipeline:
      1. Profile agent  — parse text into structured preferences
      2. Search         — call search_blocks on behalf of the user
         • if count > threshold → ask clarifying question, set status "refining", stop
         • if count ≤ threshold → proceed to Phase 3
      3. Deep analysis  — market / location / risk agents on each candidate
    """
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
        else:
            profile_result = await profile_agent.run(profile_text)
            avatar = profile_result.output
        avatar_dict = avatar.model_dump()
        homeos_case_store.set_avatar(case_id, avatar_dict)
        prefs = avatar_dict.get("preferences", {})
        logger.info(
            "[case:%s] profile done  buyer_type=%s flat_type=%s max_price=%s",
            case_id[:8], avatar_dict.get("buyer_type"), prefs.get("flat_type"), prefs.get("max_price"),
        )

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

        search_evt = {
            "event": "agent_summary", "agent": "search", "block_id": None,
            "narrative": f"Found {len(all_candidates)} matching properties.",
            "data": {
                "candidates_found": len(all_candidates),
                "candidate_ids": candidate_ids[:200],  # cap payload size
                "search_query": query_dict,
            },
        }
        yield search_evt
        homeos_case_store.append_event(case_id, search_evt)
        yield {"event": "agent_done", "agent": "search", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_done", "agent": "search", "block_id": None})

        if len(all_candidates) > _ANALYSIS_THRESHOLD and not is_mock_mode():
            # Too many — ask the user to narrow down
            question, field = _clarifying_question(prefs, len(all_candidates))
            logger.info(
                "[case:%s] REFINING  count=%d  field=%s  question=%r",
                case_id[:8], len(all_candidates), field, question[:60],
            )
            homeos_case_store.set_status(case_id, "refining")
            q_evt = {"event": "clarifying_question", "case_id": case_id, "question": question}
            yield q_evt
            homeos_case_store.append_event(case_id, q_evt)
            return  # stream ends here; user answers via /refine

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
    """
    Accepts a user refinement message for a case in 'refining' status.
    Merges the new constraints into the stored prefs, re-runs the search,
    and either asks another question or proceeds to deep analysis.
    """
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
        # Build structured Q&A prompt — pairs each clarifying question with its answer
        # so the LLM has full context across all refinement rounds.
        # NOTE: append_message above mutates case["conversation"] in-place, so the
        # new message is already present when _build_refinement_prompt reads it.
        refinement_prompt = _build_refinement_prompt(case)
        logger.info("[case:%s] refinement prompt:\n%s", case_id[:8], refinement_prompt)

        if is_mock_mode():
            avatar = mock_profile_avatar(refinement_prompt, parse_homeos_profile(refinement_prompt))
        else:
            profile_result = await profile_agent.run(refinement_prompt)
            avatar = profile_result.output
        avatar_dict = avatar.model_dump()
        prefs = avatar_dict.get("preferences", {})

        # Apply guaranteed rule-based overrides for the specific field the last
        # question was asking about. LLMs (especially small ones) may not reliably
        # map short answers like "within 600m" → commute_priority="high", so we
        # derive the field from the pipeline's last clarifying_question event and
        # parse the answer directly — no stored state needed.
        overrides = _direct_answer_overrides(user_message, case["pipeline"])
        if overrides:
            prefs.update(overrides)
            logger.info("[case:%s] direct overrides applied: %s", case_id[:8], overrides)

        avatar_dict["preferences"] = prefs
        homeos_case_store.set_avatar(case_id, avatar_dict)
        logger.info(
            "[case:%s] refined prefs  flat_type=%s max_price=%s commute=%s school=%s town=%s",
            case_id[:8], prefs.get("flat_type"), prefs.get("max_price"),
            prefs.get("commute_priority"), prefs.get("school_priority"), prefs.get("town"),
        )

        # Re-search with updated prefs
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
                "search_query": query_dict,
            },
        }
        yield search_evt
        homeos_case_store.append_event(case_id, search_evt)
        yield {"event": "agent_done", "agent": "search", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_done", "agent": "search", "block_id": None})

        if len(all_candidates) > _ANALYSIS_THRESHOLD and not is_mock_mode():
            question, field = _clarifying_question(prefs, len(all_candidates))
            logger.info("[case:%s] STILL REFINING  count=%d  field=%s", case_id[:8], len(all_candidates), field)
            homeos_case_store.set_status(case_id, "refining")
            q_evt = {"event": "clarifying_question", "case_id": case_id, "question": question}
            yield q_evt
            homeos_case_store.append_event(case_id, q_evt)
            return

        # Proceed to deep analysis
        async for evt in _deep_analysis_stream(repo, case_id, ranked, prefs):
            yield evt

    except Exception as exc:
        logger.exception("[case:%s] REFINE ERROR %s", case_id[:8], exc)
        homeos_case_store.set_status(case_id, "error")
        error_evt = {"event": "case_error", "case_id": case_id, "message": str(exc)}
        yield error_evt
        homeos_case_store.append_event(case_id, error_evt)


async def chat_in_case(case_id: str, message: str) -> AsyncGenerator[str, None]:
    """Async generator streaming an LLM answer grounded in the case evidence."""
    from pydantic_ai import Agent

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
