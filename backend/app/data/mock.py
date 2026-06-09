"""Deterministic mock-data generator for Singapore-like HDB data.

Used as the "sample data first" source until the real OneMap / HDB / LTA
pipelines are wired in. Output is reproducible for a given seed so tests can
assert exact properties.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from app.core.geo import Point
from app.core.models import (
    Block,
    BtoProject,
    BusStop,
    MrtStation,
    PlanningArea,
    School,
    Transaction,
)

FLAT_TYPES = ["2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE"]
FLAT_AREA_SQM = {"2 ROOM": 45, "3 ROOM": 67, "4 ROOM": 93, "5 ROOM": 113, "EXECUTIVE": 130}
STOREY_RANGES = ["01 TO 03", "04 TO 06", "07 TO 09", "10 TO 12", "13 TO 15"]

# A few rectangular "planning areas" tiling part of Singapore (lon/lat).
# (name, region, lon_min, lat_min, lon_max, lat_max, base_psf)
_AREAS = [
    ("TAMPINES", "EAST", 103.93, 1.34, 103.97, 1.36, 560),
    ("BEDOK", "EAST", 103.92, 1.31, 103.96, 1.33, 540),
    ("BISHAN", "CENTRAL", 103.83, 1.34, 103.86, 1.36, 700),
    ("JURONG WEST", "WEST", 103.69, 1.34, 103.73, 1.36, 480),
    ("PUNGGOL", "NORTH-EAST", 103.89, 1.39, 103.92, 1.41, 590),
]


@dataclass
class Dataset:
    planning_areas: list[PlanningArea]
    mrt_stations: list[MrtStation]
    bus_stops: list[BusStop]
    schools: list[School]
    bto_projects: list[BtoProject]
    blocks: list[Block]
    transactions: list[Transaction]


def _rect_ring(lon0, lat0, lon1, lat1):
    return [(lon0, lat0), (lon1, lat0), (lon1, lat1), (lon0, lat1)]


def generate(seed: int = 42, blocks_per_area: int = 8,
             months: int = 24, txns_per_block_month: int = 1) -> Dataset:
    rng = random.Random(seed)

    planning_areas: list[PlanningArea] = []
    area_bounds = {}
    area_psf = {}
    for i, (name, region, lo, la, lo1, la1, psf) in enumerate(_AREAS, start=1):
        planning_areas.append(PlanningArea(i, name, region, [_rect_ring(lo, la, lo1, la1)]))
        area_bounds[i] = (lo, la, lo1, la1)
        area_psf[i] = psf

    def rand_point(pa_id) -> Point:
        lo, la, lo1, la1 = area_bounds[pa_id]
        return Point(round(rng.uniform(lo, lo1), 6), round(rng.uniform(la, la1), 6))

    # Reference layers: one MRT (operational) + one future MRT per area, etc.
    mrt_stations, bus_stops, schools, bto_projects = [], [], [], []
    sid = bid_school = pid = 1
    for pa_id in area_bounds:
        p = rand_point(pa_id)
        mrt_stations.append(MrtStation(sid, f"MRT-{pa_id}", "EW", "operational", 2010, p))
        sid += 1
        pf = rand_point(pa_id)
        mrt_stations.append(MrtStation(sid, f"FUTURE-MRT-{pa_id}", "CR", "future", 2030, pf))
        sid += 1
        for b in range(3):
            bp = rand_point(pa_id)
            bus_stops.append(BusStop(f"{pa_id:02d}{b:03d}", f"Stop {pa_id}-{b}", bp))
        for s in range(2):
            schools.append(School(bid_school, f"School {bid_school}", "PRIMARY",
                                  rand_point(pa_id)))
            bid_school += 1
        bto_projects.append(BtoProject(pid, f"BTO {pa_id}", 2028, rand_point(pa_id)))
        pid += 1

    # Blocks + transactions.
    blocks: list[Block] = []
    transactions: list[Transaction] = []
    block_id = 1
    txn_id = 1
    for pa_id in area_bounds:
        for _ in range(blocks_per_area):
            pt = rand_point(pa_id)
            lease_year = rng.choice([1985, 1992, 1999, 2005, 2012, 2018])
            blocks.append(Block(
                block_id=block_id,
                block_number=str(100 + block_id),
                street_name=f"{_AREAS[pa_id - 1][0]} ST {pa_id}",
                postal_code=f"{460000 + block_id}",
                town=_AREAS[pa_id - 1][0],
                planning_area_id=None,   # resolved by ingestion (PIP)
                lease_commencement_year=lease_year,
                point=pt,
            ))
            base = area_psf[pa_id]
            for m in range(months):
                year = 2024 + (m // 12)
                month = (m % 12) + 1
                tmonth = f"{year}-{month:02d}-01"
                for _ in range(txns_per_block_month):
                    ft = rng.choice(FLAT_TYPES)
                    area = FLAT_AREA_SQM[ft] * rng.uniform(0.97, 1.03)
                    # Gentle upward PSF trend + noise.
                    psf = base * (1 + 0.004 * m) * rng.uniform(0.92, 1.08)
                    price = round(psf * area * 10.7639, -3)
                    transactions.append(Transaction(
                        transaction_id=txn_id,
                        block_id=block_id,
                        transaction_month=tmonth,
                        resale_price=float(price),
                        floor_area_sqm=round(area, 1),
                        flat_type=ft,
                        storey_range=rng.choice(STOREY_RANGES),
                    ))
                    txn_id += 1
            block_id += 1

    return Dataset(planning_areas, mrt_stations, bus_stops, schools,
                   bto_projects, blocks, transactions)
