"""Appreciation potential engine (Phase 4).

Blends historical and structural signals into a 0-100 appreciation score with a
confidence level and a risk level. This is a heuristic decision aid, NOT
financial advice — the disclaimer is returned with every result.

Factors (weights sum to 1.0):
  growth        historical median-PSF growth
  liquidity     transaction volume (easier to buy/sell)
  lease         remaining lease (longer = better)
  transport     current MRT accessibility
  future_mrt    future MRT accessibility (upside)
  bus           bus connectivity
  schools       school access
  supply        future BTO supply (more supply => lower score)
Unsupplied factors are excluded and weights renormalize (PRD rule).
"""
from __future__ import annotations

from app.repositories.base import Repository
from app.services.accessibility import block_accessibility
from app.services.analytics import block_analytics, remaining_lease_years
from app.services.future_dev import future_mrt, future_supply
from app.services.scoring import band, clamp, rising, weighted_normalized

DISCLAIMER = ("Heuristic estimate for comparison only. Not financial advice; "
              "past performance does not guarantee future returns.")

WEIGHTS = {
    "growth": 0.25,
    "liquidity": 0.10,
    "lease": 0.15,
    "transport": 0.15,
    "future_mrt": 0.10,
    "bus": 0.05,
    "schools": 0.05,
    "supply": 0.15,
}

GROWTH_FLOOR_PCT, GROWTH_CAP_PCT = -5.0, 15.0
LIQUIDITY_CAP = 60          # transactions for full liquidity score
LEASE_FLOOR, LEASE_CEIL = 40, 99


def _growth_score(growth_pct: float | None) -> float | None:
    if growth_pct is None:
        return None
    return rising(growth_pct, GROWTH_FLOOR_PCT, GROWTH_CAP_PCT)


def _confidence(txn_count: int) -> str:
    if txn_count >= LIQUIDITY_CAP:
        return "high"
    if txn_count >= 20:
        return "medium"
    return "low"


def appreciation(repo: Repository, block_id: int,
                 current_year: int | None = None) -> dict | None:
    block = repo.block(block_id)
    if block is None:
        return None

    analytics = block_analytics(repo, block_id)
    access = block_accessibility(repo, block_id)
    fmrt = future_mrt(repo, block_id)
    fsupply = future_supply(repo, block_id)

    txn_count = analytics["metrics"]["txn_count"]
    rem_lease = remaining_lease_years(block.lease_commencement_year, current_year)
    supply_pressure = fsupply["supply_pressure_pct"] if fsupply else 0.0

    factors = {
        "growth": _growth_score(analytics["metrics"]["growth_pct"]),
        "liquidity": clamp(txn_count / LIQUIDITY_CAP * 100.0),
        "lease": rising(rem_lease, LEASE_FLOOR, LEASE_CEIL),
        "transport": access["mrt_score"] if access else None,
        "future_mrt": fmrt["future_transport_growth_score"] if fmrt else None,
        "bus": access["bus_score"] if access else None,
        "schools": access["school_score"] if access else None,
        "supply": clamp(100.0 - supply_pressure),  # less supply => higher
    }
    present = {k: v for k, v in factors.items() if v is not None}
    score = weighted_normalized(present, WEIGHTS)

    # Risk rises with low lease, high supply, and low liquidity.
    risk_points = (
        (100.0 - factors["lease"]) + supply_pressure
        + (100.0 - factors["liquidity"])
    ) / 3.0
    return {
        "block_id": block_id,
        "appreciation_score": score,
        "confidence_level": _confidence(txn_count),
        "risk_level": band(risk_points),
        "factors": present,
        "disclaimer": DISCLAIMER,
    }
