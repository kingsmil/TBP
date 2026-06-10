"""Repository interface.

Two implementations satisfy this:
  * InMemoryRepository  — pure Python, used for tests and restricted envs.
  * PostgisRepository   — SQLAlchemy/GeoAlchemy2 against PostGIS (production).

Services depend only on this interface, so swapping storage is a config change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
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


class Repository(ABC):
    # --- bulk loading (ingestion) ---
    @abstractmethod
    def add_planning_areas(self, items: Iterable[PlanningArea]) -> None: ...
    @abstractmethod
    def add_mrt_stations(self, items: Iterable[MrtStation]) -> None: ...
    @abstractmethod
    def add_bus_stops(self, items: Iterable[BusStop]) -> None: ...
    @abstractmethod
    def add_schools(self, items: Iterable[School]) -> None: ...
    @abstractmethod
    def add_bto_projects(self, items: Iterable[BtoProject]) -> None: ...
    @abstractmethod
    def add_blocks(self, items: Iterable[Block]) -> None: ...
    @abstractmethod
    def add_transactions(self, items: Iterable[Transaction]) -> None: ...
    @abstractmethod
    def set_proximity(self, items: Iterable[BlockProximity]) -> None: ...

    # --- reads ---
    @abstractmethod
    def planning_areas(self) -> Sequence[PlanningArea]: ...
    @abstractmethod
    def mrt_stations(self, status: str | None = None) -> Sequence[MrtStation]: ...
    @abstractmethod
    def bus_stops(self) -> Sequence[BusStop]: ...
    @abstractmethod
    def schools(self) -> Sequence[School]: ...
    @abstractmethod
    def bto_projects(self) -> Sequence[BtoProject]: ...
    @abstractmethod
    def blocks(self) -> Sequence[Block]: ...
    @abstractmethod
    def block(self, block_id: int) -> Block | None: ...
    @abstractmethod
    def blocks_by_number(self, block_number: str) -> Sequence[Block]: ...
    @abstractmethod
    def transactions(self) -> Sequence[Transaction]: ...
    @abstractmethod
    def transactions_for_block(self, block_id: int) -> Sequence[Transaction]: ...
    @abstractmethod
    def proximity(self, block_id: int) -> BlockProximity | None: ...

    # --- active listings (HDB Flat Portal) ---
    @abstractmethod
    def add_active_listings(self, items: Iterable[ActiveListing]) -> None: ...
    @abstractmethod
    def active_listings_for_block(self, block_id: int) -> Sequence[ActiveListing]: ...
    @abstractmethod
    def active_listing(self, listing_id: int) -> ActiveListing | None: ...
