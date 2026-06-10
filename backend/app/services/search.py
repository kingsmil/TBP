"""HDB filter/search service.

Composes the four filter classes from the architecture doc:
  1. viewport bounding box          (block.point in bbox)
  2. block attributes               (town, planning area, lease year)
  3. precomputed proximity          (nearest MRT/bus distance, schools within)
  4. price / PSF band + flat type   (from transactions, via stats helper)

Returns lightweight block summaries (the /properties/search contract); full
transaction history is fetched separately on selection.
"""
from __future__ import annotations

from app.core.models import Block, BlockProximity, SearchQuery, Transaction
from app.repositories.base import Repository
from app.services.stats import StatSummary, summarize


def _in_bbox(b: Block, bbox) -> bool:
    minx, miny, maxx, maxy = bbox
    return minx <= b.point.lon <= maxx and miny <= b.point.lat <= maxy


def _passes_block_attrs(b: Block, q: SearchQuery) -> bool:
    if q.town is not None:
        # Compare with enum value (q.town is HDBTown enum, b.town is string)
        town_str = q.town.value if hasattr(q.town, 'value') else str(q.town)
        if b.town != town_str:
            return False
    if q.planning_area_id is not None and b.planning_area_id != q.planning_area_id:
        return False
    if q.min_lease_year is not None and b.lease_commencement_year < q.min_lease_year:
        return False
    if q.max_lease_year is not None and b.lease_commencement_year > q.max_lease_year:
        return False
    return True


def _passes_proximity(prox: BlockProximity | None, q: SearchQuery) -> bool:
    needs_prox = (q.max_mrt_distance_m is not None
                  or q.max_bus_distance_m is not None
                  or q.min_schools_within_1km is not None)
    if not needs_prox:
        return True
    if prox is None:
        return False
    if q.max_mrt_distance_m is not None:
        if prox.nearest_mrt_distance_m is None or prox.nearest_mrt_distance_m > q.max_mrt_distance_m:
            return False
    if q.max_bus_distance_m is not None:
        if prox.nearest_bus_distance_m is None or prox.nearest_bus_distance_m > q.max_bus_distance_m:
            return False
    if q.min_schools_within_1km is not None:
        if prox.schools_within_1km < q.min_schools_within_1km:
            return False
    return True


def _filter_transactions(txns, q: SearchQuery) -> list[Transaction]:
    out = list(txns)
    if q.flat_type is not None:
        out = [t for t in out if t.flat_type == q.flat_type]
    if q.min_floor_area is not None:
        out = [t for t in out if t.floor_area_sqm >= q.min_floor_area]
    if q.max_floor_area is not None:
        out = [t for t in out if t.floor_area_sqm <= q.max_floor_area]
    return out


def _passes_price(stats: StatSummary, q: SearchQuery) -> bool:
    if q.min_price is not None and (stats.median_price is None or stats.median_price < q.min_price):
        return False
    if q.max_price is not None and (stats.median_price is None or stats.median_price > q.max_price):
        return False
    if q.min_psf is not None and (stats.median_psf is None or stats.median_psf < q.min_psf):
        return False
    if q.max_psf is not None and (stats.median_psf is None or stats.median_psf > q.max_psf):
        return False
    return True


def _needs_transactions(q: SearchQuery) -> bool:
    return any(v is not None for v in (
        q.flat_type, q.min_floor_area, q.max_floor_area,
        q.min_price, q.max_price, q.min_psf, q.max_psf,
    ))


def _summary(b: Block, prox: BlockProximity | None, stats: StatSummary) -> dict:
    return {
        "block_id": b.block_id,
        "block_number": b.block_number,
        "street_name": b.street_name,
        "town": b.town,
        "planning_area_id": b.planning_area_id,
        "lon": b.point.lon,
        "lat": b.point.lat,
        "lease_commencement_year": b.lease_commencement_year,
        "nearest_mrt_distance_m": prox.nearest_mrt_distance_m if prox else None,
        "schools_within_1km": prox.schools_within_1km if prox else None,
        "median_psf": round(stats.median_psf, 2) if stats.median_psf else None,
        "median_price": round(stats.median_price, 2) if stats.median_price else None,
        "txn_count": stats.txn_count,
    }


def search_blocks(repo: Repository, q: SearchQuery) -> list[dict]:
    database_search = getattr(repo, "search_blocks", None)
    if callable(database_search):
        return database_search(q)

    needs_txns = _needs_transactions(q)
    results: list[dict] = []

    for b in repo.blocks():
        if q.bbox is not None and not _in_bbox(b, q.bbox):
            continue
        if not _passes_block_attrs(b, q):
            continue
        prox = repo.proximity(b.block_id)
        if not _passes_proximity(prox, q):
            continue

        txns = _filter_transactions(repo.transactions_for_block(b.block_id), q)
        if needs_txns and not txns:
            continue
        stats = summarize(txns)
        if not _passes_price(stats, q):
            continue

        results.append(_summary(b, prox, stats))

    # Cheapest median PSF first (None last), then stable by block_id.
    results.sort(key=lambda r: (r["median_psf"] is None,
                                r["median_psf"] or 0.0, r["block_id"]))
    return results[: q.limit]
