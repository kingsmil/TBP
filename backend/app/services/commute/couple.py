"""Couple mode (Phase 3).

Scores each block for two people at once: combined commute burden plus a
fairness score that rewards balanced commutes. Powers POST /couple-mode/optimize.
"""
from __future__ import annotations

from app.repositories.base import Repository
from app.services.commute.models import Person
from app.services.commute.optimizer import commute_burden, commute_score
from app.services.commute.provider import CommuteProvider

DEFAULT_WEIGHTS = {"commute": 0.6, "fairness": 0.4}


def fairness_score(weekly_a: float, weekly_b: float) -> float:
    """100 = perfectly balanced commutes; lower = more lopsided."""
    total = weekly_a + weekly_b
    if total <= 0:
        return 100.0
    return round(100.0 * (1.0 - abs(weekly_a - weekly_b) / total), 2)


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(v for v in weights.values() if v > 0)
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    return {k: v / total for k, v in weights.items() if v > 0}


def couple_optimize(repo: Repository, provider: CommuteProvider,
                    person_a: Person, person_b: Person,
                    weights: dict[str, float] | None = None,
                    limit: int = 100) -> list[dict]:
    w = _normalize(weights or DEFAULT_WEIGHTS)
    rows = []
    for b in repo.blocks():
        wk_a = commute_burden(provider, b.point, list(person_a.destinations))["weekly_minutes"]
        wk_b = commute_burden(provider, b.point, list(person_b.destinations))["weekly_minutes"]
        # Average of each person's individual commute score keeps the scale 0-100.
        commute_component = (commute_score(wk_a) + commute_score(wk_b)) / 2.0
        fairness = fairness_score(wk_a, wk_b)
        overall = round(w.get("commute", 0) * commute_component
                        + w.get("fairness", 0) * fairness, 2)
        rows.append({
            "block_id": b.block_id,
            "town": b.town,
            "planning_area_id": b.planning_area_id,
            "lon": b.point.lon,
            "lat": b.point.lat,
            f"{person_a.label}_weekly_minutes": round(wk_a, 2),
            f"{person_b.label}_weekly_minutes": round(wk_b, 2),
            "combined_weekly_minutes": round(wk_a + wk_b, 2),
            "fairness_score": fairness,
            "overall_score": overall,
        })
    rows.sort(key=lambda r: -r["overall_score"])
    return rows[:limit]


def recommended_estates(rows: list[dict], top_n: int = 3) -> list[dict]:
    """Aggregate the best blocks into recommended planning areas."""
    by_area: dict[int, list[float]] = {}
    for r in rows:
        pid = r["planning_area_id"]
        if pid is None:
            continue
        by_area.setdefault(pid, []).append(r["overall_score"])
    summary = [{"planning_area_id": pid,
                "avg_overall_score": round(sum(v) / len(v), 2),
                "block_count": len(v)}
               for pid, v in by_area.items()]
    summary.sort(key=lambda s: -s["avg_overall_score"])
    return summary[:top_n]
