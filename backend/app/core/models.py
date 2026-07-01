"""Domain entities for HDB Match (framework-agnostic dataclasses).

These mirror the schema manifest / PostGIS tables but are plain Python so the
core, services, and in-memory repository depend on nothing external.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.core.geo import Point


class HDBTown(str, Enum):
    """Singapore HDB towns (official town names in CAPS)."""
    ANG_MO_KIO = "ANG MO KIO"
    BEDOK = "BEDOK"
    BISHAN = "BISHAN"
    BUKIT_BATOK = "BUKIT BATOK"
    BUKIT_MERAH = "BUKIT MERAH"
    BUKIT_PANJANG = "BUKIT PANJANG"
    BUKIT_TIMAH = "BUKIT TIMAH"
    CENTRAL_AREA = "CENTRAL AREA"
    CHOA_CHU_KANG = "CHOA CHU KANG"
    CLEMENTI = "CLEMENTI"
    GEYLANG = "GEYLANG"
    HOUGANG = "HOUGANG"
    JURONG_EAST = "JURONG EAST"
    JURONG_WEST = "JURONG WEST"
    KALLANG_WHAMPOA = "KALLANG/WHAMPOA"
    MARINE_PARADE = "MARINE PARADE"
    PASIR_RIS = "PASIR RIS"
    PUNGGOL = "PUNGGOL"
    QUEENSTOWN = "QUEENSTOWN"
    SEMBAWANG = "SEMBAWANG"
    SENGKANG = "SENGKANG"
    SERANGOON = "SERANGOON"
    TAMPINES = "TAMPINES"
    TOA_PAYOH = "TOA PAYOH"
    WOODLANDS = "WOODLANDS"
    YISHUN = "YISHUN"


@dataclass(frozen=True)
class PlanningArea:
    planning_area_id: int
    name: str
    region: str
    # polygon as [outer_ring, *holes]; each ring is a list of (lon, lat).
    polygon: list[list[tuple[float, float]]]


@dataclass(frozen=True)
class MrtStation:
    station_id: int
    station_name: str
    line_name: str
    status: str  # 'operational' | 'future'
    opening_year: int | None
    point: Point


@dataclass(frozen=True)
class BusStop:
    bus_stop_code: str
    description: str
    point: Point


@dataclass(frozen=True)
class School:
    school_id: int
    school_name: str
    school_type: str
    point: Point


@dataclass(frozen=True)
class BtoProject:
    project_id: int
    project_name: str
    launch_year: int
    point: Point


@dataclass(frozen=True)
class Block:
    block_id: int
    block_number: str
    street_name: str
    postal_code: str
    town: str
    planning_area_id: int | None
    lease_commencement_year: int
    point: Point


@dataclass(frozen=True)
class Transaction:
    transaction_id: int
    block_id: int
    transaction_month: str  # ISO 'YYYY-MM-01'
    resale_price: float
    floor_area_sqm: float
    flat_type: str
    storey_range: str

    @property
    def floor_area_sqft(self) -> float:
        return self.floor_area_sqm * 10.7639

    @property
    def psf(self) -> float:
        return self.resale_price / self.floor_area_sqft


@dataclass(frozen=True)
class ActiveListing:
    """A currently listed flat matched to a Block.

    One Block has 0..N active listings (one per flat/unit on the market).
    listing_type is "resale" for sale listings and "rent" for rental listings.
    Agent contact fields are usually None: the portal's public API only exposes
    them for the rare agent-managed listing (contact is login-gated otherwise).
    """
    listing_id: int
    block_id: int
    block_number: str
    street_name: str
    postal_code: str
    town: str
    price: float
    flat_type: str
    floor_area_sqm: float
    storey_range: str
    remaining_lease: str
    bedroom: int | None
    bathroom: int | None
    description: str | None
    photo_path: str | None
    agent_name: str | None
    agent_phone: str | None
    agent_email: str | None
    agency_name: str | None
    managed_by_agent: bool
    last_updated: str
    listing_type: str = "resale"

    @property
    def floor_area_sqft(self) -> float:
        return self.floor_area_sqm * 10.7639


@dataclass
class BlockProximity:
    block_id: int
    nearest_mrt_station_id: int | None = None
    nearest_mrt_distance_m: float | None = None
    nearest_future_mrt_station_id: int | None = None
    nearest_future_mrt_distance_m: float | None = None
    nearest_bus_stop_code: str | None = None
    nearest_bus_distance_m: float | None = None
    schools_within_1km: int = 0
    schools_within_2km: int = 0
    bus_stops_within_400m: int = 0


@dataclass
class SearchQuery:
    """Filter inputs for /properties/search. Unset fields are ignored."""
    bbox: tuple[float, float, float, float] | None = None  # minx,miny,maxx,maxy (lon/lat)
    town: HDBTown | None = None
    planning_area_id: int | None = None
    flat_type: str | None = None
    min_floor_area: float | None = None
    max_floor_area: float | None = None
    min_lease_year: int | None = None
    max_lease_year: int | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_psf: float | None = None
    max_psf: float | None = None
    max_mrt_distance_m: float | None = None
    max_bus_distance_m: float | None = None
    min_schools_within_1km: int | None = None
    limit: int = 500
