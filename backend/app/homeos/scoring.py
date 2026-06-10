from __future__ import annotations

from typing import Literal, TypedDict


class EvidenceItem(TypedDict):
    text: str
    source: Literal["market", "location", "risk"]


def _item(text: str, source: str) -> EvidenceItem:
    return {"text": text, "source": source}


def item_texts(items: list[EvidenceItem]) -> list[str]:
    """Extract plain-text strings from attributed evidence items."""
    return [it["text"] for it in items]


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


def worth_viewing_score(
    market: dict,
    location: dict,
    risk: dict,
    prefs: dict,
    lifestyle: dict | None = None,
) -> tuple[float, list[EvidenceItem], list[EvidenceItem]]:
    score = 0.0
    reasons: list[EvidenceItem] = []
    watchouts: list[EvidenceItem] = [_item(w, "risk") for w in risk.get("watchouts", [])]

    if market.get("budget_signal") == "within_budget":
        score += 30
        reasons.append(_item("Recent comparable sales support the budget.", "market"))
    elif market.get("budget_signal") == "above_budget":
        score += 10
        watchouts.append(_item("Recent comparable sales are above the stated budget.", "market"))
    else:
        watchouts.append(_item("Price confidence is limited by sparse transaction evidence.", "market"))

    txn_count = market.get("transaction_count") or 0
    if txn_count >= 4:
        score += 20
        reasons.append(_item("Recent resale evidence is strong enough for comparison.", "market"))
    else:
        score += 8
        watchouts.append(_item("Recent resale evidence is limited.", "market"))

    for conn in location.get("connections", []):
        conn_type = conn.get("type")
        conn_signal = conn.get("signal", "")
        if conn_type == "mrt":
            if conn_signal == "strong":
                score += 18
                reasons.append(_item("MRT access fits the buyer profile.", "location"))
            elif conn_signal == "moderate":
                score += 11
                watchouts.append(_item("MRT access is moderate rather than excellent.", "location"))
            else:
                score += 4
                watchouts.append(_item("MRT access is weak for this profile.", "location"))
        if conn_type == "primary_school" and prefs.get("school_priority") == "high":
            if conn_signal == "strong":
                score += 18
                reasons.append(_item("Primary school access fits the family profile.", "location"))
            elif conn_signal == "moderate":
                score += 10
                reasons.append(_item("There is at least one primary school within 1km.", "location"))
            else:
                watchouts.append(_item("Primary school access is weak for this family profile.", "location"))

    commute = location.get("commute") or {}
    worst = commute.get("worst_commute_min")
    if commute.get("available") and worst is not None:
        resolved = [
            d for d in commute.get("destinations", [])
            if d.get("resolved") and d.get("travel_min") is not None
        ]
        if resolved:
            worst_dest = max(resolved, key=lambda d: d["travel_min"])
            if worst > 60:
                watchouts.append(_item(
                    f"Long commute to {worst_dest['name']} (~{worst_dest['travel_min']:.0f} min).",
                    "location",
                ))
            elif worst <= 30:
                score += 8
                reasons.append(_item(
                    f"Short commute to {worst_dest['name']} (~{worst_dest['travel_min']:.0f} min).",
                    "location",
                ))

    bus_routes = location.get("bus_routes") or {}
    if bus_routes.get("available") and prefs.get("bus_reliance") == "high":
        service_count = len(bus_routes.get("services", []))
        if service_count >= 8:
            score += 8
            reasons.append(_item(f"Excellent bus coverage ({service_count} services from nearest stop).", "location"))
        elif service_count >= 4:
            score += 4
            reasons.append(_item(f"Good bus coverage ({service_count} services from nearest stop).", "location"))
        elif service_count < 3:
            watchouts.append(_item(f"Limited bus coverage ({service_count} services from nearest stop).", "location"))

    score += risk.get("score_adjustment") or 0.0

    if lifestyle:
        ls = lifestyle.get("lifestyle_score")
        if ls is not None:
            # Scale 0-100 lifestyle score to a +0..+12 contribution.
            score += round((ls / 100.0) * 12.0, 1)
            if ls >= 70:
                reasons.append(_item(f"Strong lifestyle fit (score {ls:.0f}/100).", "lifestyle"))
            elif ls < 40:
                watchouts.append(_item(f"Lifestyle fit is below average (score {ls:.0f}/100).", "lifestyle"))
        for w in lifestyle.get("watchouts", []):
            watchouts.append(_item(w, "lifestyle"))

    return round(max(0.0, min(score, 100.0)), 1), reasons[:4], watchouts[:4]
