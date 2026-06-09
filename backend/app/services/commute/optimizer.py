"""Commute optimizer + heatmap (Phase 3).

Computes, for an origin (or every block), the weekly/monthly commute burden
across a set of destinations and a 0-100 commute score. Powers
POST /commute/optimize and POST /commute/heatmap.
"""
from __future__ import annotations

from app.core.geo import Point
from app.repositories.base import Repository
from app.services.accessibility import linear_decay
from app.services.commute.models import Destination
from app.services.commute.provider import CommuteProvider

WEEKS_PER_MONTH = 52.0 / 12.0
# A weekly round-trip burden at/above this many minutes scores 0.
WEEKLY_WORST_MIN = 1500.0


def commute_burden(provider: CommuteProvider, origin: Point,
                   destinations: list[Destination]) -> dict:
    """Weekly/monthly minutes spent commuting (round trips) across destinations."""
    weekly = 0.0
    per_destination = []
    for d in destinations:
        r = provider.route(origin, d.point, d.mode)
        round_trip = 2.0 * r.total_minutes
        wk = round_trip * d.visits_per_week
        weekly += wk
        per_destination.append({
            "name": d.name,
            "one_way_minutes": r.total_minutes,
            "transfers": r.transfers,
            "visits_per_week": d.visits_per_week,
            "weekly_minutes": round(wk, 2),
        })
    return {
        "weekly_minutes": round(weekly, 2),
        "monthly_minutes": round(weekly * WEEKS_PER_MONTH, 2),
        "per_destination": per_destination,
    }


def commute_score(weekly_minutes: float) -> float:
    """0-100, higher = lighter commute."""
    return linear_decay(weekly_minutes, 0.0, WEEKLY_WORST_MIN)


def score_band(score: float) -> str:
    """Heatmap colour band (green = best fit, yellow = average, red = poor)."""
    if score >= 66:
        return "green"
    if score >= 33:
        return "yellow"
    return "red"


def optimize_commute(repo: Repository, provider: CommuteProvider,
                     destinations: list[Destination], limit: int = 100) -> list[dict]:
    results = []
    for b in repo.blocks():
        burden = commute_burden(provider, b.point, destinations)
        score = commute_score(burden["weekly_minutes"])
        results.append({
            "block_id": b.block_id,
            "block_number": b.block_number,
            "town": b.town,
            "lon": b.point.lon,
            "lat": b.point.lat,
            "weekly_minutes": burden["weekly_minutes"],
            "monthly_minutes": burden["monthly_minutes"],
            "commute_score": score,
            "band": score_band(score),
        })
    # Best fit (highest score / lowest burden) first.
    results.sort(key=lambda r: -r["commute_score"])
    return results[:limit]


def commute_heatmap(repo: Repository, provider: CommuteProvider,
                    destinations: list[Destination]) -> list[dict]:
    """Lightweight per-block points for map colouring (all blocks)."""
    points = optimize_commute(repo, provider, destinations, limit=len(repo.blocks()))
    return [{"block_id": r["block_id"], "lon": r["lon"], "lat": r["lat"],
             "commute_score": r["commute_score"], "band": r["band"]}
            for r in points]
