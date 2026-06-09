"""Deterministic HomeOS sub-agents — backed by Pydantic AI agents.

Each function calls its Pydantic AI agent for an LLM narrative, enriches
the result with repository data, and returns a serialisable dict with a
'narrative' key. Function signatures are unchanged so existing callers work.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.repositories.base import Repository
from app.services.accessibility import block_accessibility
from app.services.appreciation import appreciation
from app.services.future_dev import future_mrt, future_supply
from app.services.homeos_ai_agents import (
    location_agent,
    market_agent,
    questions_agent,
    risk_agent,
)
from app.services.homeos_mock_agents import (
    is_mock_mode,
    mock_location_narrative,
    mock_market_narrative,
    mock_questions,
    mock_risk_narrative,
)
from app.services.stats import summarize


def market_analysis_agent(
    repo: Repository, block_id: int, prefs: dict[str, Any]
) -> dict[str, Any]:
    txns = list(repo.transactions_for_block(block_id))
    flat_type = prefs.get("flat_type")
    if flat_type:
        txns = [t for t in txns if t.flat_type == flat_type]
    recent = sorted(txns, key=lambda t: t.transaction_month, reverse=True)[:6]
    summary = summarize(recent)
    max_price = prefs.get("max_price")
    median_price = round(summary.median_price, 2) if summary.median_price else None
    if max_price is None or median_price is None:
        budget_signal = "unknown"
    elif median_price <= max_price:
        budget_signal = "within_budget"
    else:
        budget_signal = "above_budget"
    confidence = "high" if summary.txn_count >= 6 else "medium" if summary.txn_count >= 3 else "low"
    label = flat_type or "matching"
    evidence = {
        "transaction_count": summary.txn_count,
        "median_price": median_price,
        "median_psf": round(summary.median_psf, 2) if summary.median_psf else None,
        "window_months": 6,
        "budget_signal": budget_signal,
        "confidence": confidence,
    }
    if is_mock_mode():
        narrative = mock_market_narrative(evidence, prefs)
    else:
        prompt = (
            f"block_id={block_id}, flat_type={flat_type}, max_price={max_price}, "
            f"transaction_count={summary.txn_count}, median_price={median_price}, "
            f"budget_signal={budget_signal}, confidence={confidence}"
        )
        result = asyncio.run(market_agent.run(prompt))
        narrative = result.output.narrative or (
            f"{summary.txn_count} similar {label} transactions support price confidence."
        )
    evidence["summary"] = narrative
    evidence["narrative"] = narrative
    return evidence


def location_graph_agent(repo: Repository, block_id: int) -> dict[str, Any]:
    prox = repo.proximity(block_id)
    if prox is None:
        return {"connections": [], "narrative": "No proximity data available."}
    mrt_dist = prox.nearest_mrt_distance_m
    mrt_signal = (
        "strong" if mrt_dist is not None and mrt_dist <= 500
        else "moderate" if mrt_dist is not None and mrt_dist <= 1000
        else "weak"
    )
    school_count = prox.schools_within_1km
    school_signal = "strong" if school_count >= 2 else "moderate" if school_count == 1 else "weak"
    connections = [
        {
            "type": "mrt",
            "name": "Nearest operational MRT",
            "distance_m": mrt_dist,
            "signal": mrt_signal,
        },
        {
            "type": "primary_school",
            "name": "Primary schools within 1km",
            "count": school_count,
            "signal": school_signal,
        },
    ]
    if is_mock_mode():
        narrative = mock_location_narrative(connections)
    else:
        prompt = f"mrt_distance={mrt_dist}, mrt_signal={mrt_signal}, schools_1km={school_count}, school_signal={school_signal}"
        result = asyncio.run(location_agent.run(prompt))
        narrative = result.output.narrative or f"MRT {mrt_dist}m ({mrt_signal}), {school_count} schools ({school_signal})."
    return {"connections": connections, "narrative": narrative}


def risk_value_agent(
    repo: Repository, block_id: int, prefs: dict[str, Any]
) -> dict[str, Any]:
    app_data = appreciation(repo, block_id)
    future_mrt_data = future_mrt(repo, block_id)
    future_supply_data = future_supply(repo, block_id)
    accessibility = block_accessibility(repo, block_id)
    watchouts: list[str] = []
    score_adjustment = 0.0

    if app_data and app_data.get("appreciation_score") is not None:
        score_adjustment += min(12.0, app_data["appreciation_score"] / 10)
    if app_data and app_data.get("risk_level") == "high" and prefs.get("risk_tolerance") == "low":
        watchouts.append("Appreciation model flags elevated risk for a low-risk buyer.")
        score_adjustment -= 8.0
    if future_supply_data and future_supply_data.get("supply_risk_level") == "high":
        watchouts.append("Nearby future supply may weigh on appreciation.")
        score_adjustment -= 4.0

    evidence = {
        "appreciation": app_data,
        "future_mrt": future_mrt_data,
        "future_supply": future_supply_data,
        "accessibility": accessibility,
        "watchouts": watchouts,
        "score_adjustment": score_adjustment,
    }
    if is_mock_mode():
        narrative = mock_risk_narrative(evidence)
    else:
        prompt = (
            f"appreciation_score={app_data.get('appreciation_score') if app_data else None}, "
            f"risk_level={app_data.get('risk_level') if app_data else None}, "
            f"supply_risk={future_supply_data.get('supply_risk_level') if future_supply_data else None}, "
            f"risk_tolerance={prefs.get('risk_tolerance')}, "
            f"watchouts={watchouts}"
        )
        result = asyncio.run(risk_agent.run(prompt))
        narrative = result.output.narrative or f"{len(watchouts)} risk signals identified."
    evidence["narrative"] = narrative
    return evidence


def viewing_questions_agent(evidence: dict[str, Any]) -> list[str]:
    base_questions = [
        "Which floor range is the unit in?",
        "Is the unit facing a main road or MRT track?",
        "Are recent comparable transactions renovated or original condition?",
        "Are there ethnic quota or extension restrictions?",
    ]
    market = evidence.get("market", {})
    location = evidence.get("location", {})
    if market.get("confidence") == "low":
        base_questions.append("Why is there limited recent resale evidence for this block or flat type?")
    if any(c.get("signal") == "weak" for c in location.get("connections", [])):
        base_questions.append("What is the realistic walking route and time to the nearest MRT or school?")
    if is_mock_mode():
        extra = [q for q in mock_questions(evidence) if q and q not in base_questions]
    else:
        prompt = (
            f"market_confidence={market.get('confidence')}, "
            f"connections={location.get('connections', [])}, "
            f"watchouts={evidence.get('risk', {}).get('watchouts', [])}"
        )
        result = asyncio.run(questions_agent.run(prompt))
        extra = [q for q in result.output.questions if q and q not in base_questions]
    return (base_questions + extra)[:6]


def worth_viewing_score(
    market: dict[str, Any],
    location: dict[str, Any],
    risk: dict[str, Any],
    prefs: dict[str, Any],
) -> tuple[float, list[str], list[str]]:
    score = 0.0
    reasons: list[str] = []
    watchouts: list[str] = list(risk.get("watchouts", []))

    if market.get("budget_signal") == "within_budget":
        score += 30
        reasons.append("Recent comparable sales support the budget.")
    elif market.get("budget_signal") == "above_budget":
        score += 10
        watchouts.append("Recent comparable sales are above the stated budget.")
    else:
        watchouts.append("Price confidence is limited by sparse transaction evidence.")

    txn_count = market.get("transaction_count") or 0
    if txn_count >= 4:
        score += 20
        reasons.append("Recent resale evidence is strong enough for comparison.")
    else:
        score += 8
        watchouts.append("Recent resale evidence is limited.")

    for conn in location.get("connections", []):
        if conn["type"] == "mrt":
            if conn["signal"] == "strong":
                score += 18
                reasons.append("MRT access fits the buyer profile.")
            elif conn["signal"] == "moderate":
                score += 11
                watchouts.append("MRT access is moderate rather than excellent.")
            else:
                score += 4
                watchouts.append("MRT access is weak for this profile.")
        if conn["type"] == "primary_school" and prefs.get("school_priority") == "high":
            if conn["signal"] == "strong":
                score += 18
                reasons.append("Primary school access fits the family profile.")
            elif conn["signal"] == "moderate":
                score += 10
                reasons.append("There is at least one primary school within 1km.")
            else:
                watchouts.append("Primary school access is weak for this family profile.")

    score += risk.get("score_adjustment") or 0.0
    return round(max(0.0, min(score, 100.0)), 1), reasons[:4], watchouts[:4]
