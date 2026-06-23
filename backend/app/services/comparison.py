"""Estate comparison service (Phase 2).

Builds a side-by-side metric set per estate by composing the analytics and
accessibility services: price, growth, transaction volume, lease profile, and
MRT/bus/school accessibility. Powers GET /comparison/estates.
"""
from __future__ import annotations

import os

from app.repositories.base import Repository
from app.services.cache import SWRCache
from app.services.accessibility import (
    bus_score, combined_score, estate_accessibility, future_mrt_score,
    mrt_score, school_score,
)
from app.services.analytics import (
    estate_analytics, growth_pct, remaining_lease_years,
)
from app.services.stats import monthly_summaries, summarize


def lease_profile(repo: Repository, block_ids: list[int],
                  current_year: int | None = None) -> dict:
    years = [remaining_lease_years(repo.block(b).lease_commencement_year, current_year)
             for b in block_ids if repo.block(b) is not None]
    if not years:
        return {"avg_remaining_lease": None, "min_remaining_lease": None,
                "max_remaining_lease": None}
    return {
        "avg_remaining_lease": round(sum(years) / len(years), 1),
        "min_remaining_lease": min(years),
        "max_remaining_lease": max(years),
    }


def estate_metrics(repo: Repository, planning_area_id: int,
                   flat_type: str | None = None) -> dict | None:
    analytics = estate_analytics(repo, planning_area_id, flat_type)
    if analytics is None:
        return None
    block_ids = [b.block_id for b in repo.blocks()
                 if b.planning_area_id == planning_area_id]
    name = next((pa.name for pa in repo.planning_areas()
                 if pa.planning_area_id == planning_area_id), None)
    access = estate_accessibility(repo, planning_area_id)
    return {
        "planning_area_id": planning_area_id,
        "name": name,
        "block_count": analytics["block_count"],
        "median_psf": analytics["metrics"]["median_psf"],
        "median_price": analytics["metrics"]["median_price"],
        "growth_pct": analytics["metrics"]["growth_pct"],
        "txn_count": analytics["metrics"]["txn_count"],
        "lease_profile": lease_profile(repo, block_ids),
        "accessibility": {
            "mrt_score": access["mrt_score"] if access else None,
            "future_mrt_score": access["future_mrt_score"] if access else None,
            "bus_score": access["bus_score"] if access else None,
            "school_score": access["school_score"] if access else None,
            "combined_score": access["combined_score"] if access else None,
        },
    }


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def compare_estates(repo: Repository, planning_area_ids: list[int] | None = None,
                    flat_type: str | None = None) -> list[dict]:
    """Side-by-side metrics for every (or selected) planning area.

    Single-pass: blocks, transactions and proximity are each loaded ONCE and
    grouped by area, rather than re-querying per area (which is O(areas x all
    transactions) and becomes very slow with years of data).
    """
    blocks = list(repo.blocks())
    block_by_id = {b.block_id: b for b in blocks}
    areas = {pa.planning_area_id: pa for pa in repo.planning_areas()}
    prox_by_id = {p.block_id: p for p in repo.all_proximity()}

    blocks_by_area: dict[int, list] = {}
    for b in blocks:
        if b.planning_area_id is not None:
            blocks_by_area.setdefault(b.planning_area_id, []).append(b)

    txns_by_area: dict[int, list] = {}
    for t in repo.transactions():
        b = block_by_id.get(t.block_id)
        if b is None or b.planning_area_id is None:
            continue
        if flat_type is not None and t.flat_type != flat_type:
            continue
        txns_by_area.setdefault(b.planning_area_id, []).append(t)

    target = planning_area_ids if planning_area_ids is not None else list(blocks_by_area.keys())
    rows = []
    for pid in target:
        area_blocks = blocks_by_area.get(pid)
        if not area_blocks:
            continue
        txns = txns_by_area.get(pid, [])
        s = summarize(txns)
        proxs = [prox_by_id[b.block_id] for b in area_blocks if b.block_id in prox_by_id]
        years = [remaining_lease_years(b.lease_commencement_year) for b in area_blocks]
        rows.append({
            "planning_area_id": pid,
            "name": areas[pid].name if pid in areas else None,
            "block_count": len(area_blocks),
            "median_psf": s.median_psf,
            "median_price": s.median_price,
            "growth_pct": growth_pct(monthly_summaries(txns)),
            "txn_count": s.txn_count,
            "lease_profile": {
                "avg_remaining_lease": round(sum(years) / len(years), 1) if years else None,
                "min_remaining_lease": min(years) if years else None,
                "max_remaining_lease": max(years) if years else None,
            },
            "accessibility": {
                "mrt_score": _avg([mrt_score(p) for p in proxs]),
                "future_mrt_score": _avg([future_mrt_score(p) for p in proxs]),
                "bus_score": _avg([bus_score(p) for p in proxs]),
                "school_score": _avg([school_score(p) for p in proxs]),
                "combined_score": _avg([combined_score(p) for p in proxs]),
            },
        })
    # Most accessible first, then cheapest PSF.
    rows.sort(key=lambda r: (
        -(r["accessibility"]["combined_score"] or 0.0),
        r["median_psf"] if r["median_psf"] is not None else float("inf"),
    ))
    return rows


# The full comparison is identical for every user and only changes when data
# changes, so cache it and refresh in the background rather than recomputing per
# request. Default TTL 6h; refresh is stale-while-revalidate (never blocks).
_CACHE = SWRCache(ttl=float(os.environ.get("COMPARISON_CACHE_TTL", str(6 * 3600))))


def compare_estates_cached(repo: Repository, planning_area_ids: list[int] | None = None,
                           flat_type: str | None = None) -> list[dict]:
    """Cached full-comparison; a specific estate subset bypasses the cache."""
    if planning_area_ids is not None:
        return compare_estates(repo, planning_area_ids, flat_type)
    key = flat_type or "__all__"
    return _CACHE.get(key, lambda: compare_estates(repo, None, flat_type))


def warm_comparison_cache(repo: Repository) -> None:
    """Pre-compute the default comparison in the background (call at startup)."""
    _CACHE.warm("__all__", lambda: compare_estates(repo, None, None))
