"""HomeOS Agent: profile parsing, HDB investigation, and viewing handoff."""
from __future__ import annotations

import re
from typing import Any


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


async def investigate_stream(
    repo: Repository,
    profile_text: str,
    limit: int = 5,
) -> AsyncGenerator[dict, None]:
    """Async generator yielding AgentEvent dicts for SSE streaming."""
    case = homeos_case_store.create_case(profile_text)
    case_id = case["case_id"]

    try:
        # --- Profile Agent ---
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

        profile_summary = {
            "event": "agent_summary", "agent": "profile", "block_id": None,
            "narrative": avatar.summary, "data": avatar_dict,
        }
        yield profile_summary
        homeos_case_store.append_event(case_id, profile_summary)

        yield {"event": "agent_done", "agent": "profile", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_done", "agent": "profile", "block_id": None})

        # --- Per-block agents ---
        from app.services.homeos_agents import (
            location_graph_agent,
            market_analysis_agent,
            risk_value_agent,
            viewing_questions_agent,
            worth_viewing_score,
        )

        prefs = avatar_dict.get("preferences", {})
        rows = []

        for block in list(repo.blocks())[:limit * 3]:
            block_id = block.block_id
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

                # Run sync agent (which internally calls asyncio.run) in a thread
                # so it gets its own event loop and doesn't conflict with ours.
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

            if prefs.get("flat_type") and market_evidence.get("transaction_count", 0) == 0:
                continue

            score, reasons, watchouts = worth_viewing_score(market_evidence, location_evidence, risk_evidence, prefs)
            rows.append({
                "block_id": block_id,
                "block_number": block.block_number,
                "street_name": block.street_name,
                "town": block.town,
                "worth_viewing_score": score,
                "verdict": _verdict(score),
                "confidence": _confidence(market_evidence.get("transaction_count", 0)),
                "top_reasons": reasons,
                "top_watchouts": watchouts,
            })

            if len(rows) >= limit:
                break

        rows.sort(key=lambda r: (-r["worth_viewing_score"], r["block_id"]))
        shortlist = rows[:limit]
        homeos_case_store.set_shortlist(case_id, shortlist)
        homeos_case_store.set_status(case_id, "done")

        done_evt = {"event": "case_done", "case_id": case_id, "shortlist": shortlist}
        yield done_evt
        homeos_case_store.append_event(case_id, done_evt)

    except Exception as exc:
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
