"""Recommendation engine (Phase 5).

Ranks blocks by a composite of lifestyle fit and appreciation potential
(commute folds into lifestyle when destinations are supplied), and attaches
human-readable reasons drawn from the strongest contributing factors. Also
aggregates to recommended estates.
"""
from __future__ import annotations

from app.repositories.base import Repository
from app.services.appreciation import appreciation
from app.services.commute.models import Destination
from app.services.commute.provider import CommuteProvider
from app.services.lifestyle import block_lifestyle
from app.services.scoring import weighted_normalized

DEFAULT_WEIGHTS = {"lifestyle": 0.6, "appreciation": 0.4}

_FACTOR_PHRASES = {
    "commute": "short commute",
    "transport": "strong transport access",
    "schools": "good school access",
    "affordability": "good value for money",
}


def _reasons(lifestyle_factors: dict[str, float], appreciation_score: float | None,
             max_reasons: int = 3) -> list[str]:
    reasons: list[str] = []
    for key, _ in sorted(lifestyle_factors.items(), key=lambda kv: -kv[1]):
        if lifestyle_factors[key] >= 60 and key in _FACTOR_PHRASES:
            reasons.append(_FACTOR_PHRASES[key])
    if appreciation_score is not None and appreciation_score >= 60:
        reasons.append("solid appreciation potential")
    return reasons[:max_reasons] or ["balanced overall profile"]


def recommend(repo: Repository, provider: CommuteProvider | None = None,
              destinations: list[Destination] | None = None,
              weights: dict[str, float] | None = None, limit: int = 10) -> dict:
    w = weights or DEFAULT_WEIGHTS
    results = []
    for b in repo.blocks():
        life = block_lifestyle(repo, b.block_id, provider=provider,
                               destinations=destinations)
        appr = appreciation(repo, b.block_id)
        components = {
            "lifestyle": life["lifestyle_score"] if life else None,
            "appreciation": appr["appreciation_score"] if appr else None,
        }
        present = {k: v for k, v in components.items() if v is not None}
        overall = weighted_normalized(present, w)
        if overall is None:
            continue
        results.append({
            "block_id": b.block_id,
            "block_number": b.block_number,
            "town": b.town,
            "planning_area_id": b.planning_area_id,
            "lon": b.point.lon,
            "lat": b.point.lat,
            "overall_score": overall,
            "lifestyle_score": components["lifestyle"],
            "appreciation_score": components["appreciation"],
            "reasons": _reasons(life["factors"] if life else {},
                                components["appreciation"]),
        })
    results.sort(key=lambda r: -r["overall_score"])
    top = results[:limit]
    return {"count": len(results), "results": top,
            "recommended_estates": _recommend_estates(top)}


def _recommend_estates(rows: list[dict], top_n: int = 3) -> list[dict]:
    by_area: dict[int, list[float]] = {}
    for r in rows:
        pid = r["planning_area_id"]
        if pid is None:
            continue
        by_area.setdefault(pid, []).append(r["overall_score"])
    summary = [{"planning_area_id": pid,
                "avg_score": round(sum(v) / len(v), 2), "block_count": len(v)}
               for pid, v in by_area.items()]
    summary.sort(key=lambda s: -s["avg_score"])
    return summary[:top_n]
