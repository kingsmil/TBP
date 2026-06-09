"""Dream Home Finder (Phase 4).

Takes the user's hard requirements (budget, flat type, lease, MRT distance,
schools) plus optional commute destinations, filters to matching blocks, then
ranks them by a match score that blends the components the user actually cares
about. Powers POST /dream-home-finder.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.models import SearchQuery
from app.repositories.base import Repository
from app.services.analytics import remaining_lease_years
from app.services.appreciation import appreciation
from app.services.commute.models import Destination
from app.services.commute.optimizer import commute_burden, commute_score
from app.services.commute.provider import CommuteProvider
from app.services.lifestyle import block_lifestyle
from app.services.scoring import clamp, weighted_normalized
from app.services.search import search_blocks

DEFAULT_WEIGHTS = {
    "commute": 0.30,
    "lifestyle": 0.30,
    "appreciation": 0.25,
    "budget_fit": 0.15,
}


@dataclass
class DreamCriteria:
    max_price: float | None = None
    flat_type: str | None = None
    min_remaining_lease: int | None = None
    max_mrt_distance_m: float | None = None
    min_schools_within_1km: int | None = None
    destinations: list[Destination] = field(default_factory=list)
    weights: dict[str, float] | None = None
    limit: int = 20


def _budget_fit(median_price: float | None, max_price: float | None) -> float | None:
    if max_price is None or median_price is None or max_price <= 0:
        return None
    # Candidates are already <= budget; more headroom => higher score.
    return clamp((max_price - median_price) / max_price * 100.0)


def dream_home_finder(repo: Repository, criteria: DreamCriteria,
                      provider: CommuteProvider | None = None) -> dict:
    # Hard filters via the existing search service.
    q = SearchQuery(
        flat_type=criteria.flat_type,
        max_price=criteria.max_price,
        max_mrt_distance_m=criteria.max_mrt_distance_m,
        min_schools_within_1km=criteria.min_schools_within_1km,
        limit=10_000,
    )
    candidates = search_blocks(repo, q)
    weights = criteria.weights or DEFAULT_WEIGHTS

    results = []
    for c in candidates:
        block = repo.block(c["block_id"])
        rem = remaining_lease_years(block.lease_commencement_year)
        if criteria.min_remaining_lease is not None and rem < criteria.min_remaining_lease:
            continue

        components: dict[str, float | None] = {
            "budget_fit": _budget_fit(c["median_price"], criteria.max_price),
        }
        life = block_lifestyle(repo, block.block_id, provider=provider,
                               destinations=criteria.destinations or None)
        components["lifestyle"] = life["lifestyle_score"] if life else None
        appr = appreciation(repo, block.block_id)
        components["appreciation"] = appr["appreciation_score"] if appr else None
        if provider is not None and criteria.destinations:
            weekly = commute_burden(provider, block.point, criteria.destinations)["weekly_minutes"]
            components["commute"] = commute_score(weekly)

        present = {k: v for k, v in components.items() if v is not None}
        match = weighted_normalized(present, weights)
        results.append({
            "block_id": block.block_id,
            "block_number": block.block_number,
            "town": block.town,
            "planning_area_id": block.planning_area_id,
            "lon": block.point.lon,
            "lat": block.point.lat,
            "median_price": c["median_price"],
            "remaining_lease_years": rem,
            "match_score": match,
            "components": present,
        })

    results.sort(key=lambda r: -(r["match_score"] or 0.0))
    top = results[: criteria.limit]
    return {
        "match_count": len(results),
        "results": top,
        "recommended_estates": _recommend_estates(top),
    }


def _recommend_estates(rows: list[dict], top_n: int = 3) -> list[dict]:
    by_area: dict[int, list[float]] = {}
    for r in rows:
        pid = r["planning_area_id"]
        if pid is None or r["match_score"] is None:
            continue
        by_area.setdefault(pid, []).append(r["match_score"])
    summary = [{"planning_area_id": pid,
                "avg_match_score": round(sum(v) / len(v), 2),
                "block_count": len(v)}
               for pid, v in by_area.items()]
    summary.sort(key=lambda s: -s["avg_match_score"])
    return summary[:top_n]
