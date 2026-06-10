"""Assemble a case-file response from already-stored case events (no recompute)."""
from typing import Any

from app.homeos import case_store
from app.homeos.scoring import item_texts
from app.homeos.sync_agents import base_viewing_questions

_AGENTS = ("market", "location", "lifestyle", "risk")


def assemble_case_file_from_case(case_id: str, block_id: int) -> dict[str, Any] | None:
    case = case_store.get_case(case_id)
    if case is None:
        return None

    events = [e for e in case.get("pipeline", []) if e.get("block_id") == block_id]
    if not events:
        return None

    evidence_by_agent: dict[str, dict] = {}
    tool_calls_by_agent: dict[str, list] = {}
    narrative_by_agent: dict[str, str] = {}
    for e in events:
        agent = e.get("agent")
        if agent not in _AGENTS:
            continue
        if e.get("event") == "agent_data":
            evidence_by_agent[agent] = e.get("data", {})
        elif e.get("event") == "tool_calls":
            tool_calls_by_agent.setdefault(agent, []).extend(e.get("tool_calls", []))
        elif e.get("event") == "agent_summary":
            narrative_by_agent[agent] = e.get("narrative", "")

    market = evidence_by_agent.get("market")
    if market is None:
        return None  # block was never analysed in this case

    location = evidence_by_agent.get("location", {})
    risk = evidence_by_agent.get("risk", {})

    row = next((r for r in case.get("shortlist", []) if r["block_id"] == block_id), None)
    if row is None:
        return None

    watchouts = row.get("top_watchouts", [])
    questions = base_viewing_questions(
        {"market": market, "location": location, "risk": risk}
    )

    trace = [
        {
            "agent": agent,
            "narrative": narrative_by_agent.get(agent, ""),
            "tool_calls": tool_calls_by_agent.get(agent, []),
        }
        for agent in _AGENTS
        if agent in evidence_by_agent
    ]

    return {
        "block_id": block_id,
        "block_number": row["block_number"],
        "street_name": row["street_name"],
        "town": row["town"],
        "verdict": row["verdict"],
        "worth_viewing_score": row["worth_viewing_score"],
        "confidence": row["confidence"],
        "top_reasons": row.get("top_reasons", []),
        "top_watchouts": watchouts,
        "evidence": {
            "recent_sales": {
                "transaction_count": market.get("transaction_count", 0),
                "median_price": market.get("median_price"),
                "median_psf": market.get("median_psf"),
                "window_months": market.get("window_months", 6),
                "summary": market.get("summary") or market.get("narrative", ""),
            },
            "connections": location.get("connections", []),
            "risks": item_texts(watchouts),
            "future_signals": {
                "future_mrt": risk.get("future_mrt"),
                "future_supply": risk.get("future_supply"),
            },
            "agent_questions": questions,
        },
        "trace": trace,
    }
