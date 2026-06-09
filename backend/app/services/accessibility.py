"""Accessibility scoring (Phase 2).

Turns the precomputed block_proximity numbers into normalized 0-100 sub-scores
for MRT, bus, and schools, plus a weighted combined score. All thresholds are
declared as named constants so they are easy to tune and are covered by tests.

Per the PRD, unsupplied factors are excluded rather than treated as average:
combined_score normalizes over whatever weights are provided.
"""
from __future__ import annotations

from app.core.models import BlockProximity
from app.repositories.base import Repository

# --- thresholds (metres / counts) ---
MRT_BEST_M, MRT_WORST_M = 200.0, 2000.0
FUTURE_MRT_BEST_M, FUTURE_MRT_WORST_M = 200.0, 2500.0
BUS_BEST_M, BUS_WORST_M = 100.0, 800.0
BUS_DENSITY_CAP = 5          # bus stops within 400 m for full density score
SCHOOL_1KM_CAP = 3
SCHOOL_2KM_CAP = 6

DEFAULT_WEIGHTS = {"mrt": 0.45, "bus": 0.25, "school": 0.30}


def linear_decay(value: float | None, best: float, worst: float) -> float:
    """100 at <= best, 0 at >= worst, linear in between (clamped)."""
    if value is None:
        return 0.0
    if value <= best:
        return 100.0
    if value >= worst:
        return 0.0
    return round(100.0 * (worst - value) / (worst - best), 2)


def _capped_pct(count: int | None, cap: int) -> float:
    if not count or cap <= 0:
        return 0.0
    return round(min(count, cap) / cap * 100.0, 2)


def mrt_score(prox: BlockProximity) -> float:
    return linear_decay(prox.nearest_mrt_distance_m, MRT_BEST_M, MRT_WORST_M)


def future_mrt_score(prox: BlockProximity) -> float:
    return linear_decay(prox.nearest_future_mrt_distance_m,
                        FUTURE_MRT_BEST_M, FUTURE_MRT_WORST_M)


def bus_score(prox: BlockProximity) -> float:
    proximity = linear_decay(prox.nearest_bus_distance_m, BUS_BEST_M, BUS_WORST_M)
    density = _capped_pct(prox.bus_stops_within_400m, BUS_DENSITY_CAP)
    return round(0.5 * proximity + 0.5 * density, 2)


def school_score(prox: BlockProximity) -> float:
    near = _capped_pct(prox.schools_within_1km, SCHOOL_1KM_CAP)
    wider = _capped_pct(prox.schools_within_2km, SCHOOL_2KM_CAP)
    return round(0.7 * near + 0.3 * wider, 2)


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(v for v in weights.values() if v > 0)
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    return {k: v / total for k, v in weights.items() if v > 0}


def combined_score(prox: BlockProximity,
                   weights: dict[str, float] | None = None) -> float:
    w = _normalize_weights(weights or DEFAULT_WEIGHTS)
    parts = {"mrt": mrt_score(prox), "bus": bus_score(prox),
             "school": school_score(prox)}
    return round(sum(w[k] * parts[k] for k in w), 2)


def block_accessibility(repo: Repository, block_id: int,
                        weights: dict[str, float] | None = None) -> dict | None:
    prox = repo.proximity(block_id)
    if prox is None:
        return None
    return {
        "block_id": block_id,
        "mrt_score": mrt_score(prox),
        "future_mrt_score": future_mrt_score(prox),
        "bus_score": bus_score(prox),
        "school_score": school_score(prox),
        "combined_score": combined_score(prox, weights),
        "raw": {
            "nearest_mrt_distance_m": prox.nearest_mrt_distance_m,
            "nearest_future_mrt_distance_m": prox.nearest_future_mrt_distance_m,
            "nearest_bus_distance_m": prox.nearest_bus_distance_m,
            "schools_within_1km": prox.schools_within_1km,
            "schools_within_2km": prox.schools_within_2km,
            "bus_stops_within_400m": prox.bus_stops_within_400m,
        },
    }


def estate_accessibility(repo: Repository, planning_area_id: int,
                         weights: dict[str, float] | None = None) -> dict | None:
    block_ids = [b.block_id for b in repo.blocks()
                 if b.planning_area_id == planning_area_id]
    scores = [block_accessibility(repo, bid, weights) for bid in block_ids]
    scores = [s for s in scores if s is not None]
    if not scores:
        return None
    keys = ("mrt_score", "future_mrt_score", "bus_score", "school_score",
            "combined_score")
    agg = {k: round(sum(s[k] for s in scores) / len(scores), 2) for k in keys}
    agg.update({"planning_area_id": planning_area_id, "block_count": len(scores)})
    return agg
