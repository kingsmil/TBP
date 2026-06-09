"""Shared scoring primitives used by the Phase 4 engines.

Kept tiny and pure so appreciation / dream-home logic stays consistent and
testable. The "weighted_normalized" helper encodes the PRD rule that unsupplied
factors are excluded (weights renormalize over what is present).
"""
from __future__ import annotations


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def rising(value: float | None, low: float, high: float) -> float:
    """0 at <= low, 100 at >= high, linear in between (higher value = better)."""
    if value is None:
        return 0.0
    if value <= low:
        return 0.0
    if value >= high:
        return 100.0
    return round(100.0 * (value - low) / (high - low), 2)


def capped_pct(count: int | None, cap: int) -> float:
    """0..100 share of `cap` (count >= cap => 100)."""
    if not count or cap <= 0:
        return 0.0
    return round(min(count, cap) / cap * 100.0, 2)


def weighted_normalized(factors: dict[str, float],
                        weights: dict[str, float]) -> float | None:
    """Weighted mean over factors present (non-None) with a positive weight."""
    active = {k: weights[k] for k, v in factors.items()
              if v is not None and weights.get(k, 0) > 0}
    total = sum(active.values())
    if total <= 0:
        return None
    return round(sum((active[k] / total) * factors[k] for k in active), 2)


def band(score: float, low: float = 33.0, high: float = 66.0) -> str:
    """Generic 3-way band: 'low' / 'medium' / 'high'."""
    if score < low:
        return "low"
    if score < high:
        return "medium"
    return "high"
