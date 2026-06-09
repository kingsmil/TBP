"""Shared statistics helpers for transactions.

Pure functions used by both the search service (price/PSF bands) and the
analytics service (dashboard rollups). The median here matches PostGIS
percentile_cont(0.5) (linear interpolation at the midpoint).
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from app.core.models import Transaction


@dataclass(frozen=True)
class StatSummary:
    median_psf: float | None
    avg_psf: float | None
    median_price: float | None
    avg_price: float | None
    txn_count: int


def _median(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def summarize(transactions: Iterable[Transaction]) -> StatSummary:
    txns = list(transactions)
    psf = [t.psf for t in txns]
    price = [t.resale_price for t in txns]
    return StatSummary(
        median_psf=_median(psf),
        avg_psf=_mean(psf),
        median_price=_median(price),
        avg_price=_mean(price),
        txn_count=len(txns),
    )


def group_by(transactions: Iterable[Transaction],
             key: Callable[[Transaction], object]) -> dict[object, list[Transaction]]:
    out: dict[object, list[Transaction]] = defaultdict(list)
    for t in transactions:
        out[key(t)].append(t)
    return dict(out)


def monthly_summaries(transactions: Iterable[Transaction]) -> list[dict]:
    """Time series of StatSummary per transaction_month, sorted ascending."""
    grouped = group_by(transactions, lambda t: t.transaction_month)
    rows = []
    for month in sorted(grouped):
        s = summarize(grouped[month])
        rows.append({
            "month": month,
            "median_psf": s.median_psf,
            "avg_psf": s.avg_psf,
            "median_price": s.median_price,
            "avg_price": s.avg_price,
            "txn_count": s.txn_count,
        })
    return rows
