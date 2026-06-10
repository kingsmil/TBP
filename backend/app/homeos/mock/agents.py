"""Mock narrative generators — replace LLM calls in demo/mock mode."""
from __future__ import annotations

from typing import Any

from app.homeos.models.avatar import HomeOSAvatar, HomeOSPreferences


def mock_profile_avatar(profile_text: str, parsed: dict[str, Any]) -> HomeOSAvatar:
    prefs = parsed.get("preferences", {})
    flat_type = prefs.get("flat_type") or "any flat type"
    max_price = prefs.get("max_price")
    budget = f" under ${max_price:,.0f}" if max_price else ""
    summary = (
        f"Mock profile: demo buyer looking for {flat_type}{budget}, with "
        f"{prefs.get('school_priority', 'medium')} school priority and "
        f"{prefs.get('commute_priority', 'medium')} commute priority."
    )
    return HomeOSAvatar(
        label="Mock HomeOS Agent",
        buyer_type=parsed.get("buyer_type", "family"),
        summary=summary,
        preferences=HomeOSPreferences(**prefs),
    )


def mock_market_narrative(evidence: dict[str, Any], prefs: dict[str, Any]) -> str:
    txn_count = evidence.get("transaction_count", 0)
    median_price = evidence.get("median_price")
    signal = evidence.get("budget_signal", "unknown").replace("_", " ")
    price_text = f"median ${median_price:,.0f}" if median_price else "no reliable median yet"
    flat_type = prefs.get("flat_type") or "matching flats"
    return (
        f"Mock market: {txn_count} recent {flat_type} transactions show {price_text}; "
        f"budget signal is {signal}."
    )


def mock_location_narrative(connections: list[dict[str, Any]]) -> str:
    mrt = next((c for c in connections if c.get("type") == "mrt"), {})
    schools = next((c for c in connections if c.get("type") == "primary_school"), {})
    mrt_dist = mrt.get("distance_m")
    mrt_text = f"{mrt_dist:.0f}m to MRT" if isinstance(mrt_dist, int | float) else "MRT distance unavailable"
    return (
        f"Mock location: {mrt_text} with {mrt.get('signal', 'unknown')} access; "
        f"{schools.get('count', 0)} primary schools within 1km."
    )


def mock_risk_narrative(evidence: dict[str, Any]) -> str:
    watchouts = evidence.get("watchouts", [])
    adjustment = evidence.get("score_adjustment", 0.0)
    if watchouts:
        return f"Mock risk: {len(watchouts)} watchout found; score adjustment is {adjustment:.1f}."
    return f"Mock risk: no major watchouts surfaced; score adjustment is {adjustment:.1f}."


def mock_lifestyle_narrative(evidence: dict[str, Any]) -> str:
    score = evidence.get("lifestyle_score")
    band = evidence.get("commute_band", "unknown")
    if score is not None:
        return f"Mock lifestyle: overall score {score}, commute band {band}."
    return f"Mock lifestyle: commute band {band}; detailed scoring not available in mock mode."


def mock_questions(evidence: dict[str, Any]) -> list[str]:
    market = evidence.get("market", {})
    location = evidence.get("location", {})
    questions = [
        "Can the agent confirm the unit floor, facing, and renovation condition?",
        "Were the closest comparable sales renovated or original condition?",
        "Are there ethnic quota, extension, or contra restrictions for this unit?",
    ]
    if market.get("confidence") in {"low", "medium"}:
        questions.append("Why is recent resale evidence limited for this exact flat type?")
    if any(c.get("signal") != "strong" for c in location.get("connections", [])):
        questions.append("What is the actual walking route to MRT and nearby schools?")
    return questions[:6]


def mock_chat_answer(case: dict[str, Any], message: str) -> str:
    summaries = [
        e.get("narrative", "")
        for e in case.get("pipeline", [])
        if e.get("event") == "agent_summary" and e.get("narrative")
    ]
    shortlist = case.get("shortlist", [])
    top = shortlist[0] if shortlist else None
    if top:
        block_text = (
            f"Top block is Blk {top['block_number']} {top['street_name']} "
            f"with score {top['worth_viewing_score']}."
        )
    else:
        block_text = "No shortlist block is available yet."
    first_summary = summaries[0] if summaries else "The pipeline has not produced a summary yet."
    return (
        "Mock HomeOS: based on the stored pipeline, "
        f"{block_text} First pipeline signal: {first_summary} "
        f"Your question was: {message}"
    )


def mock_outreach_message(
    listing: Any,
    avatar_summary: str | None,
    contact_name: str | None,
    availability: list[str],
) -> str:
    """Deterministic outreach copy for demo/mock mode and CI."""
    who = f"My name is {contact_name}. " if contact_name else ""
    profile = f" A bit about us: {avatar_summary}" if avatar_summary else ""
    avail = (
        f" We could view on {'; '.join(availability)}." if availability else ""
    )
    return (
        f"Hi! {who}I saw your {listing.flat_type} listing at "
        f"Blk {listing.block_number} {listing.street_name} and I'm very interested. "
        f"Could I ask: how is the {listing.remaining_lease} remaining lease reflected "
        f"in the asking price, and has the unit been renovated recently? "
        f"Is the {listing.storey_range} storey unit still available for viewing?"
        f"{avail}{profile}"
    )
