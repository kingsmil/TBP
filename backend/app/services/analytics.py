"""Analytics service: estate- and block-level dashboard data.

In production these read the materialized views (mv_block_monthly_stats,
mv_estate_monthly_stats). Here we compute the same shapes directly from the
in-memory transactions so the logic is identical and testable. Charts consume
these shapes directly (PSF over time, volume, PSF by flat type, etc.).
"""
from __future__ import annotations

import datetime as _dt

from app.core.models import Transaction
from app.repositories.base import Repository
from app.services.stats import group_by, monthly_summaries, summarize


def _current_year() -> int:
    return _dt.date.today().year


def remaining_lease_years(lease_commencement_year: int,
                          current_year: int | None = None) -> int:
    current_year = current_year or _current_year()
    return max(0, 99 - (current_year - lease_commencement_year))


def _filter_flat_type(txns, flat_type):
    return [t for t in txns if flat_type is None or t.flat_type == flat_type]


def psf_by_flat_type(transactions) -> list[dict]:
    grouped = group_by(transactions, lambda t: t.flat_type)
    rows = []
    for ft in sorted(grouped):
        s = summarize(grouped[ft])
        rows.append({"flat_type": ft, "median_psf": s.median_psf,
                     "txn_count": s.txn_count})
    return rows


def volume_over_time(monthly: list[dict]) -> list[dict]:
    return [{"month": r["month"], "txn_count": r["txn_count"]} for r in monthly]


def growth_pct(monthly: list[dict]) -> float | None:
    """Percent change in median PSF from first to last month with data."""
    points = [r for r in monthly if r["median_psf"] is not None]
    if len(points) < 2:
        return None
    first, last = points[0]["median_psf"], points[-1]["median_psf"]
    if not first:
        return None
    return round((last - first) / first * 100, 2)


def psf_by_lease_age(repo: Repository, transactions,
                     current_year: int | None = None, bucket: int = 10,
                     block_by_id: dict | None = None) -> list[dict]:
    """Group transactions by their block's remaining-lease bucket.

    Pass `block_by_id` to avoid a per-transaction block lookup (one query each).
    """
    def get_block(bid):
        return block_by_id.get(bid) if block_by_id is not None else repo.block(bid)

    def key(t: Transaction):
        b = get_block(t.block_id)
        if b is None:
            return None
        rem = remaining_lease_years(b.lease_commencement_year, current_year)
        return (rem // bucket) * bucket
    grouped = group_by((t for t in transactions if key(t) is not None), key)
    rows = []
    for lease_bucket in sorted(grouped):
        s = summarize(grouped[lease_bucket])
        rows.append({"remaining_lease_bucket": lease_bucket,
                     "median_psf": s.median_psf, "txn_count": s.txn_count})
    return rows


def price_vs_mrt_distance(repo: Repository, block_ids, flat_type=None,
                          txns_by_block: dict | None = None,
                          prox_by_id: dict | None = None) -> list[dict]:
    """Pass `txns_by_block` / `prox_by_id` to avoid a per-block query each."""
    rows = []
    for bid in block_ids:
        raw = txns_by_block.get(bid, []) if txns_by_block is not None else repo.transactions_for_block(bid)
        txns = _filter_flat_type(raw, flat_type)
        prox = prox_by_id.get(bid) if prox_by_id is not None else repo.proximity(bid)
        if not txns or prox is None or prox.nearest_mrt_distance_m is None:
            continue
        s = summarize(txns)
        rows.append({"block_id": bid,
                     "nearest_mrt_distance_m": prox.nearest_mrt_distance_m,
                     "median_psf": s.median_psf})
    return rows


def _metrics_dict(summary, **extra) -> dict:
    d = {
        "median_psf": summary.median_psf,
        "avg_psf": summary.avg_psf,
        "median_price": summary.median_price,
        "avg_price": summary.avg_price,
        "txn_count": summary.txn_count,
    }
    d.update(extra)
    return d


def block_analytics(repo: Repository, block_id: int,
                    flat_type: str | None = None) -> dict | None:
    block = repo.block(block_id)
    if block is None:
        return None
    txns_all = list(repo.transactions_for_block(block_id))
    txns = _filter_flat_type(txns_all, flat_type)
    monthly = monthly_summaries(txns)
    return {
        "scope": "block",
        "block_id": block_id,
        "town": block.town,
        "planning_area_id": block.planning_area_id,
        "metrics": _metrics_dict(
            summarize(txns),
            remaining_lease_years=remaining_lease_years(block.lease_commencement_year),
            growth_pct=growth_pct(monthly),
        ),
        "psf_over_time": monthly,
        "volume_over_time": volume_over_time(monthly),
        "psf_by_flat_type": psf_by_flat_type(txns_all),
    }


def estate_analytics(repo: Repository, planning_area_id: int,
                     flat_type: str | None = None) -> dict | None:
    # Preload blocks, the estate's transactions, and proximity ONCE, then pass
    # them down — otherwise the lease-age and PSF-vs-MRT helpers do thousands of
    # per-row/per-block queries (this was a ~9s endpoint on real data).
    blocks = list(repo.blocks())
    block_by_id = {b.block_id: b for b in blocks}
    block_ids = [b.block_id for b in blocks if b.planning_area_id == planning_area_id]
    if not block_ids:
        return None
    id_set = set(block_ids)
    txns_by_block: dict[int, list] = {}
    for t in repo.transactions():
        if t.block_id in id_set:
            txns_by_block.setdefault(t.block_id, []).append(t)
    txns_all = [t for ts in txns_by_block.values() for t in ts]
    txns = _filter_flat_type(txns_all, flat_type)
    prox_by_id = {p.block_id: p for p in repo.all_proximity()}
    monthly = monthly_summaries(txns)
    return {
        "scope": "estate",
        "planning_area_id": planning_area_id,
        "block_count": len(block_ids),
        "metrics": _metrics_dict(summarize(txns), growth_pct=growth_pct(monthly)),
        "psf_over_time": monthly,
        "volume_over_time": volume_over_time(monthly),
        "psf_by_flat_type": psf_by_flat_type(txns_all),
        "psf_by_lease_age": psf_by_lease_age(repo, txns_all, block_by_id=block_by_id),
        "price_vs_mrt_distance": price_vs_mrt_distance(
            repo, block_ids, flat_type, txns_by_block=txns_by_block, prox_by_id=prox_by_id),
    }


def estate_comparison(repo: Repository, flat_type: str | None = None) -> list[dict]:
    """One row per planning area with headline metrics + growth."""
    rows = []
    for pa in repo.planning_areas():
        a = estate_analytics(repo, pa.planning_area_id, flat_type)
        if a is None:
            continue
        rows.append({
            "planning_area_id": pa.planning_area_id,
            "name": pa.name,
            "median_psf": a["metrics"]["median_psf"],
            "growth_pct": a["metrics"]["growth_pct"],
            "txn_count": a["metrics"]["txn_count"],
            "block_count": a["block_count"],
        })
    rows.sort(key=lambda r: (r["median_psf"] is None, r["median_psf"] or 0.0))
    return rows
