"""Lifestyle score (Phase 3).

Blends available factors into a single 0-100 score. Per the PRD, factors the
user does not supply are EXCLUDED (not treated as average): the weights are
normalized over whichever factors are actually present, so a blank factor has
zero influence rather than a neutral one.

Factors available in Phase 3: commute, transport, schools, affordability.
(Greenery, amenities, appreciation arrive in later phases and slot in here.)
"""
from __future__ import annotations

from app.core.geo import Point
from app.repositories.base import Repository
from app.services.accessibility import block_accessibility, linear_decay
from app.services.commute.models import Destination
from app.services.commute.optimizer import commute_burden, commute_score
from app.services.commute.provider import CommuteProvider
from app.services.stats import summarize

DEFAULT_WEIGHTS = {
    "commute": 0.35,
    "transport": 0.25,
    "schools": 0.20,
    "affordability": 0.20,
}


def lifestyle_score(factors: dict[str, float],
                    weights: dict[str, float] | None = None) -> float | None:
    """Weighted mean over factors that are present (non-None) with a positive weight."""
    weights = weights or DEFAULT_WEIGHTS
    active = {k: weights[k] for k, v in factors.items()
              if v is not None and weights.get(k, 0) > 0}
    total = sum(active.values())
    if total <= 0:
        return None
    return round(sum((active[k] / total) * factors[k] for k in active), 2)


def _block_median_psf(repo: Repository, block_id: int) -> float | None:
    return summarize(repo.transactions_for_block(block_id)).median_psf


def _psf_bounds(repo: Repository) -> tuple[float, float] | None:
    psfs = [p for b in repo.blocks()
            if (p := _block_median_psf(repo, b.block_id)) is not None]
    if not psfs:
        return None
    return min(psfs), max(psfs)


def affordability_score(repo: Repository, block_id: int,
                        bounds: tuple[float, float] | None = None) -> float | None:
    """Cheaper relative to the dataset => higher score."""
    psf = _block_median_psf(repo, block_id)
    if psf is None:
        return None
    bounds = bounds or _psf_bounds(repo)
    if bounds is None:
        return None
    lo, hi = bounds
    if hi <= lo:
        return 100.0
    # linear_decay: best (cheapest) -> 100, worst (priciest) -> 0.
    return linear_decay(psf, lo, hi)


def block_lifestyle(repo: Repository, block_id: int,
                    provider: CommuteProvider | None = None,
                    destinations: list[Destination] | None = None,
                    weights: dict[str, float] | None = None,
                    psf_bounds: tuple[float, float] | None = None) -> dict | None:
    if repo.block(block_id) is None:
        return None
    factors: dict[str, float | None] = {}

    access = block_accessibility(repo, block_id)
    if access is not None:
        factors["transport"] = round((access["mrt_score"] + access["bus_score"]) / 2, 2)
        factors["schools"] = access["school_score"]

    factors["affordability"] = affordability_score(repo, block_id, psf_bounds)

    if provider is not None and destinations:
        b = repo.block(block_id)
        weekly = commute_burden(provider, b.point, destinations)["weekly_minutes"]
        factors["commute"] = commute_score(weekly)

    present = {k: v for k, v in factors.items() if v is not None}
    return {
        "block_id": block_id,
        "lifestyle_score": lifestyle_score(present, weights),
        "factors": present,
    }
