"""Estate comparison service (Phase 2).

Builds a side-by-side metric set per estate by composing the analytics and
accessibility services: price, growth, transaction volume, lease profile, and
MRT/bus/school accessibility. Powers GET /comparison/estates.
"""
from __future__ import annotations

from app.repositories.base import Repository
from app.services.accessibility import estate_accessibility
from app.services.analytics import estate_analytics, remaining_lease_years


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


def compare_estates(repo: Repository, planning_area_ids: list[int] | None = None,
                    flat_type: str | None = None) -> list[dict]:
    if planning_area_ids is None:
        planning_area_ids = [pa.planning_area_id for pa in repo.planning_areas()]
    rows = [estate_metrics(repo, pid, flat_type) for pid in planning_area_ids]
    rows = [r for r in rows if r is not None]
    # Most accessible first, then cheapest PSF.
    rows.sort(key=lambda r: (
        -(r["accessibility"]["combined_score"] or 0.0),
        r["median_psf"] if r["median_psf"] is not None else float("inf"),
    ))
    return rows
