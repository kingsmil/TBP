from __future__ import annotations


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

    commute = location.get("commute") or {}
    worst = commute.get("worst_commute_min")
    if commute.get("available") and worst is not None and worst > 60:
        resolved = [
            d for d in commute.get("destinations", [])
            if d.get("resolved") and d.get("travel_min") is not None
        ]
        if resolved:
            worst_dest = max(resolved, key=lambda d: d["travel_min"])
            watchouts.append(
                f"Long commute to {worst_dest['name']} (~{worst_dest['travel_min']:.0f} min)."
            )

    score += risk.get("score_adjustment") or 0.0
    return round(max(0.0, min(score, 100.0)), 1), reasons[:4], watchouts[:4]
