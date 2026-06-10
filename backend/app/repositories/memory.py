"""In-memory repository: pure-Python implementation of the Repository interface.

Backs tests and restricted environments. Stores entities in dicts/lists and
exposes the same reads the PostGIS repository will. Spatial work (proximity,
point-in-polygon) is done by the ingestion pipeline using app.core.geo, so the
results match the PostGIS semantics.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

from app.core.models import (
    ActiveListing,
    Block,
    BlockProximity,
    BtoProject,
    BusStop,
    MrtStation,
    PlanningArea,
    School,
    Transaction,
)
from app.repositories.base import Repository


class InMemoryRepository(Repository):
    def __init__(self) -> None:
        self._planning_areas: dict[int, PlanningArea] = {}
        self._mrt: dict[int, MrtStation] = {}
        self._bus: dict[str, BusStop] = {}
        self._schools: dict[int, School] = {}
        self._bto: dict[int, BtoProject] = {}
        self._blocks: dict[int, Block] = {}
        self._txns: list[Transaction] = []
        self._txns_by_block: dict[int, list[Transaction]] = defaultdict(list)
        self._proximity: dict[int, BlockProximity] = {}
        self._active: dict[int, ActiveListing] = {}
        self._bus_routes: list[dict] = []

    # --- bulk loading ---
    def add_planning_areas(self, items: Iterable[PlanningArea]) -> None:
        for it in items:
            self._planning_areas[it.planning_area_id] = it

    def add_mrt_stations(self, items: Iterable[MrtStation]) -> None:
        for it in items:
            self._mrt[it.station_id] = it

    def add_bus_stops(self, items: Iterable[BusStop]) -> None:
        for it in items:
            self._bus[it.bus_stop_code] = it

    def add_schools(self, items: Iterable[School]) -> None:
        for it in items:
            self._schools[it.school_id] = it

    def add_bto_projects(self, items: Iterable[BtoProject]) -> None:
        for it in items:
            self._bto[it.project_id] = it

    def add_blocks(self, items: Iterable[Block]) -> None:
        for it in items:
            self._blocks[it.block_id] = it

    def add_transactions(self, items: Iterable[Transaction]) -> None:
        for it in items:
            self._txns.append(it)
            self._txns_by_block[it.block_id].append(it)

    def set_proximity(self, items: Iterable[BlockProximity]) -> None:
        for it in items:
            self._proximity[it.block_id] = it

    def add_bus_routes(self, items: Iterable[dict]) -> None:
        """Route rows: {service_no, direction, stop_sequence, bus_stop_code}.
        In-memory only; PostGIS routes are ingested by sync_bus_network.py."""
        self._bus_routes.extend(items)

    # --- reads ---
    def planning_areas(self) -> Sequence[PlanningArea]:
        return list(self._planning_areas.values())

    def mrt_stations(self, status: str | None = None) -> Sequence[MrtStation]:
        vals = list(self._mrt.values())
        if status is not None:
            vals = [m for m in vals if m.status == status]
        return vals

    def bus_stops(self) -> Sequence[BusStop]:
        return list(self._bus.values())

    def schools(self) -> Sequence[School]:
        return list(self._schools.values())

    def bto_projects(self) -> Sequence[BtoProject]:
        return list(self._bto.values())

    def blocks(self) -> Sequence[Block]:
        return list(self._blocks.values())

    def block(self, block_id: int) -> Block | None:
        return self._blocks.get(block_id)

    def blocks_by_number(self, block_number: str) -> Sequence[Block]:
        bn = block_number.strip().upper()
        return [b for b in self._blocks.values() if b.block_number.upper() == bn]

    def transactions(self) -> Sequence[Transaction]:
        return list(self._txns)

    def transactions_for_block(self, block_id: int) -> Sequence[Transaction]:
        return list(self._txns_by_block.get(block_id, []))

    def proximity(self, block_id: int) -> BlockProximity | None:
        return self._proximity.get(block_id)

    def bus_stop_reach(self, bus_stop_code: str) -> dict | None:
        origin = self._bus.get(bus_stop_code)
        if origin is None:
            return None

        boardings: dict[tuple[str, int], int] = {}
        for r in self._bus_routes:
            if r["bus_stop_code"] == bus_stop_code:
                key = (r["service_no"], r["direction"])
                boardings[key] = min(boardings.get(key, r["stop_sequence"]), r["stop_sequence"])

        services: list[dict] = []
        reachable: dict[str, dict] = {}
        for (service_no, direction), seq in sorted(boardings.items()):
            downstream = sorted(
                (
                    r for r in self._bus_routes
                    if r["service_no"] == service_no
                    and r["direction"] == direction
                    and r["stop_sequence"] >= seq
                ),
                key=lambda r: r["stop_sequence"],
            )
            stops = []
            for r in downstream:
                stop_entity = self._bus.get(r["bus_stop_code"])
                if stop_entity is None:
                    continue
                stop = {
                    "bus_stop_code": stop_entity.bus_stop_code,
                    "description": stop_entity.description,
                    "lat": stop_entity.point.lat,
                    "lon": stop_entity.point.lon,
                    "stop_sequence": r["stop_sequence"],
                }
                stops.append(stop)
                if stop_entity.bus_stop_code != bus_stop_code:
                    reachable[stop_entity.bus_stop_code] = stop
            services.append({"service_no": service_no, "direction": direction, "stops": stops})

        return {
            "origin": {
                "bus_stop_code": origin.bus_stop_code,
                "description": origin.description,
                "lat": origin.point.lat,
                "lon": origin.point.lon,
            },
            "service_count": len(services),
            "reachable_stop_count": len(reachable),
            "services": services,
            "reachable_stops": list(reachable.values()),
        }

    # --- active listings (HDB Flat Portal) ---
    def add_active_listings(self, items: Iterable[ActiveListing]) -> None:
        for it in items:
            self._active[it.listing_id] = it

    def active_listings_for_block(self, block_id: int) -> Sequence[ActiveListing]:
        return [a for a in self._active.values() if a.block_id == block_id]

    def active_listing(self, listing_id: int) -> ActiveListing | None:
        return self._active.get(listing_id)
