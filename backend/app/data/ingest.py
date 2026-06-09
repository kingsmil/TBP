"""Ingestion pipeline (mock-data path).

Mirrors the production pipeline shape: validate -> load -> resolve derived
fields (planning-area FK via point-in-polygon) -> compute proximity. The
spatial derivations use app.core.geo so they match PostGIS semantics.

Returns an IngestReport so callers can assert data quality (validation gate).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from app.core.geo import Point, count_within_m, nearest, point_in_polygon
from app.core.models import Block, BlockProximity
from app.data.mock import Dataset
from app.repositories.base import Repository

# Singapore bounding box for a basic validity gate.
SG_BBOX = (103.6, 1.20, 104.10, 1.48)  # minx, miny, maxx, maxy


@dataclass
class IngestReport:
    blocks_loaded: int = 0
    transactions_loaded: int = 0
    blocks_with_planning_area: int = 0
    blocks_rejected: int = 0
    proximity_rows: int = 0
    rejected_reasons: list[str] = field(default_factory=list)


def _in_sg(p: Point) -> bool:
    x0, y0, x1, y1 = SG_BBOX
    return x0 <= p.lon <= x1 and y0 <= p.lat <= y1


def _resolve_planning_area(block: Block, areas) -> int | None:
    for pa in areas:
        if point_in_polygon(block.point, pa.polygon):
            return pa.planning_area_id
    return None


def compute_proximity(blocks, mrt_ops, mrt_future, bus_stops, schools) -> list[BlockProximity]:
    """Equivalent of the block_proximity refresh job (KNN + radius counts)."""
    mrt_ops_pts = [(m.station_id, m.point) for m in mrt_ops]
    mrt_fut_pts = [(m.station_id, m.point) for m in mrt_future]
    bus_pts = [(b.bus_stop_code, b.point) for b in bus_stops]
    school_pts = [(s.school_id, s.point) for s in schools]

    rows = []
    for b in blocks:
        prox = BlockProximity(block_id=b.block_id)
        if mrt_ops_pts:
            sid, _, dist = nearest(b.point, mrt_ops_pts)
            prox.nearest_mrt_station_id = sid
            prox.nearest_mrt_distance_m = round(dist, 2)
        if mrt_fut_pts:
            sid, _, dist = nearest(b.point, mrt_fut_pts)
            prox.nearest_future_mrt_station_id = sid
            prox.nearest_future_mrt_distance_m = round(dist, 2)
        if bus_pts:
            code, _, dist = nearest(b.point, bus_pts)
            prox.nearest_bus_stop_code = code
            prox.nearest_bus_distance_m = round(dist, 2)
        prox.schools_within_1km = count_within_m(b.point, school_pts, 1000)
        prox.schools_within_2km = count_within_m(b.point, school_pts, 2000)
        prox.bus_stops_within_400m = count_within_m(b.point, bus_pts, 400)
        rows.append(prox)
    return rows


def ingest(dataset: Dataset, repo: Repository) -> IngestReport:
    report = IngestReport()

    repo.add_planning_areas(dataset.planning_areas)
    repo.add_mrt_stations(dataset.mrt_stations)
    repo.add_bus_stops(dataset.bus_stops)
    repo.add_schools(dataset.schools)
    repo.add_bto_projects(dataset.bto_projects)

    # Validate + resolve planning-area FK for each block.
    accepted: list[Block] = []
    for b in dataset.blocks:
        if not _in_sg(b.point):
            report.blocks_rejected += 1
            report.rejected_reasons.append(f"block {b.block_id} outside SG bbox")
            continue
        pa_id = _resolve_planning_area(b, dataset.planning_areas)
        b = replace(b, planning_area_id=pa_id)
        if pa_id is not None:
            report.blocks_with_planning_area += 1
        accepted.append(b)

    repo.add_blocks(accepted)
    report.blocks_loaded = len(accepted)

    # Transactions only for accepted blocks.
    valid_ids = {b.block_id for b in accepted}
    txns = [t for t in dataset.transactions if t.block_id in valid_ids]
    repo.add_transactions(txns)
    report.transactions_loaded = len(txns)

    # Proximity (precomputed spatial cache).
    prox = compute_proximity(
        accepted,
        [m for m in dataset.mrt_stations if m.status == "operational"],
        [m for m in dataset.mrt_stations if m.status == "future"],
        dataset.bus_stops,
        dataset.schools,
    )
    repo.set_proximity(prox)
    report.proximity_rows = len(prox)
    return report
