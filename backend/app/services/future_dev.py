"""Future development analysis (Phase 4).

Future MRT impact and future BTO supply for a block. Future MRT distance is
precomputed in block_proximity; future BTO supply is computed on demand from
bto_projects (few rows). A production optimization would precompute the BTO
count into block_proximity, mirroring the other proximity columns.
"""
from __future__ import annotations

from app.core.geo import count_within_m, distance_m
from app.repositories.base import Repository
from app.services.accessibility import future_mrt_score
from app.services.scoring import band, capped_pct

FUTURE_SUPPLY_RADIUS_M = 2000.0
FUTURE_SUPPLY_CAP = 3   # >= this many nearby future BTOs => max supply pressure


def future_mrt(repo: Repository, block_id: int) -> dict | None:
    block = repo.block(block_id)
    prox = repo.proximity(block_id)
    if block is None or prox is None:
        return None
    station = next((m for m in repo.mrt_stations("future")
                    if m.station_id == prox.nearest_future_mrt_station_id), None)
    return {
        "block_id": block_id,
        "nearest_future_mrt_station_id": prox.nearest_future_mrt_station_id,
        "station_name": station.station_name if station else None,
        "line_name": station.line_name if station else None,
        "opening_year": station.opening_year if station else None,
        "distance_m": prox.nearest_future_mrt_distance_m,
        "future_transport_growth_score": future_mrt_score(prox),
    }


def future_supply(repo: Repository, block_id: int,
                  radius_m: float = FUTURE_SUPPLY_RADIUS_M) -> dict | None:
    block = repo.block(block_id)
    if block is None:
        return None
    projects = []
    for p in repo.bto_projects():
        d = distance_m(block.point, p.point)
        if d <= radius_m:
            projects.append({"project_id": p.project_id, "name": p.project_name,
                             "launch_year": p.launch_year, "distance_m": round(d, 2)})
    count = len(projects)
    supply_pressure_pct = capped_pct(count, FUTURE_SUPPLY_CAP)
    return {
        "block_id": block_id,
        "radius_m": radius_m,
        "future_bto_count": count,
        "projects": sorted(projects, key=lambda x: x["distance_m"]),
        "supply_pressure_pct": supply_pressure_pct,
        # Higher supply pressure => higher supply risk.
        "supply_risk_level": band(supply_pressure_pct),
    }
