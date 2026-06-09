"""Single source of truth for the HDB Match data model.

This pure-Python manifest describes every table and column once. It is used by:
  * the in-memory repository (to validate mock data shape),
  * the test suite (to cross-check the PostGIS SQL migrations against it),
  * documentation / introspection.

Geospatial-first conventions encoded here:
  * Every spatial table carries `geom` (EPSG:4326, canonical) AND a generated
    `geom_svy21` (EPSG:3414, metric) column.
  * Distance/area maths use SVY21; display/interchange uses WGS84.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Coordinate reference systems (see architecture doc, section 3).
SRID_WGS84 = 4326
SRID_SVY21 = 3414
SRID_WEBMERCATOR = 3857


@dataclass(frozen=True)
class Column:
    name: str
    pg_type: str
    nullable: bool = True
    generated: bool = False
    note: str = ""


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    pk: tuple[str, ...] = ()
    spatial: bool = False
    geom_type: str | None = None          # 'Point' | 'MultiPolygon' | ...
    partition_by: str | None = None        # column name for RANGE partitioning
    is_materialized_view: bool = False
    unique_index: tuple[str, ...] = ()      # required for REFRESH ... CONCURRENTLY

    def column_names(self) -> set[str]:
        return {c.name for c in self.columns}


def _geom_columns(geom_type: str) -> tuple[Column, ...]:
    """Standard dual-geometry pair every spatial table gets."""
    return (
        Column("geom", f"geometry({geom_type},{SRID_WGS84})", nullable=False,
               note="canonical WGS84 geometry"),
        Column("geom_svy21", f"geometry({geom_type},{SRID_SVY21})", nullable=False,
               generated=True,
               note="ST_Transform(geom,3414) STORED; metric ops only"),
    )


def table(name: str, columns, **kwargs) -> Table:
    return Table(name=name, columns=tuple(columns), **kwargs)


# --- Reference spatial layers -------------------------------------------------

PLANNING_AREAS = table(
    "planning_areas",
    [
        Column("planning_area_id", "bigint", nullable=False),
        Column("name", "text", nullable=False),
        Column("region", "text"),
        *_geom_columns("MultiPolygon"),
    ],
    pk=("planning_area_id",), spatial=True, geom_type="MultiPolygon",
)

MRT_STATIONS = table(
    "mrt_stations",
    [
        Column("station_id", "bigint", nullable=False),
        Column("station_name", "text", nullable=False),
        Column("line_name", "text"),
        Column("status", "text", nullable=False, note="'operational' | 'future'"),
        Column("opening_year", "smallint"),
        *_geom_columns("Point"),
    ],
    pk=("station_id",), spatial=True, geom_type="Point",
)

BUS_STOPS = table(
    "bus_stops",
    [
        Column("bus_stop_code", "text", nullable=False),
        Column("description", "text"),
        *_geom_columns("Point"),
    ],
    pk=("bus_stop_code",), spatial=True, geom_type="Point",
)

SCHOOLS = table(
    "schools",
    [
        Column("school_id", "bigint", nullable=False),
        Column("school_name", "text", nullable=False),
        Column("school_type", "text"),
        *_geom_columns("Point"),
    ],
    pk=("school_id",), spatial=True, geom_type="Point",
)

BTO_PROJECTS = table(
    "bto_projects",
    [
        Column("project_id", "bigint", nullable=False),
        Column("project_name", "text", nullable=False),
        Column("launch_year", "smallint"),
        *_geom_columns("Point"),
    ],
    pk=("project_id",), spatial=True, geom_type="Point",
)

# --- Core spatial entity ------------------------------------------------------

HDB_BLOCKS = table(
    "hdb_blocks",
    [
        Column("block_id", "bigint", nullable=False),
        Column("block_number", "text", nullable=False),
        Column("street_name", "text", nullable=False),
        Column("postal_code", "text"),
        Column("town", "text"),
        Column("planning_area_id", "bigint", note="FK planning_areas; PIP-resolved"),
        Column("lease_commencement_year", "smallint"),
        *_geom_columns("Point"),
        # NOTE: remaining_lease_years is intentionally NOT here. It depends on the
        # current date (now() is non-immutable, disallowed in GENERATED columns),
        # so it is exposed via a view / refreshed stats column instead.
    ],
    pk=("block_id",), spatial=True, geom_type="Point",
)

# --- Transactions (partitioned, append-mostly) --------------------------------

HDB_TRANSACTIONS = table(
    "hdb_transactions",
    [
        Column("transaction_id", "bigint", nullable=False),
        Column("block_id", "bigint", nullable=False),
        Column("transaction_month", "date", nullable=False),
        Column("resale_price", "numeric(12,2)", nullable=False),
        Column("floor_area_sqm", "numeric(8,2)", nullable=False),
        Column("floor_area_sqft", "numeric(12,4)", generated=True,
               note="floor_area_sqm * 10.7639 STORED"),
        Column("psf", "numeric(12,4)", generated=True,
               note="resale_price / (floor_area_sqm*10.7639) STORED"),
        Column("flat_type", "text", nullable=False),
        Column("storey_range", "text"),
    ],
    pk=("transaction_id", "transaction_month"),  # PK must include partition key
    partition_by="transaction_month",
)

# --- Precomputed proximity (spatial hot-path cache) ---------------------------

BLOCK_PROXIMITY = table(
    "block_proximity",
    [
        Column("block_id", "bigint", nullable=False),
        Column("nearest_mrt_station_id", "bigint"),
        Column("nearest_mrt_distance_m", "numeric(10,2)"),
        Column("nearest_future_mrt_station_id", "bigint"),
        Column("nearest_future_mrt_distance_m", "numeric(10,2)"),
        Column("nearest_bus_stop_code", "text"),
        Column("nearest_bus_distance_m", "numeric(10,2)"),
        Column("schools_within_1km", "smallint"),
        Column("schools_within_2km", "smallint"),
        Column("bus_stops_within_400m", "smallint"),
    ],
    pk=("block_id",),
)

# --- Bus routes (stored now, graph later) -------------------------------------

BUS_ROUTES = table(
    "bus_routes",
    [
        Column("service_no", "text", nullable=False),
        Column("direction", "smallint", nullable=False),
        Column("bus_stop_code", "text", nullable=False),
        Column("stop_sequence", "smallint", nullable=False),
        Column("distance_km", "numeric(8,3)"),
    ],
    pk=("service_no", "direction", "stop_sequence"),
)

# --- Analytics materialized views ---------------------------------------------

MV_BLOCK_MONTHLY_STATS = table(
    "mv_block_monthly_stats",
    [
        Column("block_id", "bigint", nullable=False),
        Column("transaction_month", "date", nullable=False),
        Column("flat_type", "text", nullable=False),
        Column("median_psf", "numeric(12,4)"),
        Column("avg_psf", "numeric(12,4)"),
        Column("median_price", "numeric(12,2)"),
        Column("avg_price", "numeric(12,2)"),
        Column("txn_count", "integer"),
    ],
    is_materialized_view=True,
    unique_index=("block_id", "transaction_month", "flat_type"),
)

MV_ESTATE_MONTHLY_STATS = table(
    "mv_estate_monthly_stats",
    [
        Column("planning_area_id", "bigint", nullable=False),
        Column("transaction_month", "date", nullable=False),
        Column("flat_type", "text", nullable=False),
        Column("median_psf", "numeric(12,4)"),
        Column("avg_psf", "numeric(12,4)"),
        Column("median_price", "numeric(12,2)"),
        Column("avg_price", "numeric(12,2)"),
        Column("txn_count", "integer"),
    ],
    is_materialized_view=True,
    unique_index=("planning_area_id", "transaction_month", "flat_type"),
)


MANIFEST: tuple[Table, ...] = (
    PLANNING_AREAS,
    MRT_STATIONS,
    BUS_STOPS,
    SCHOOLS,
    BTO_PROJECTS,
    HDB_BLOCKS,
    HDB_TRANSACTIONS,
    BLOCK_PROXIMITY,
    BUS_ROUTES,
    MV_BLOCK_MONTHLY_STATS,
    MV_ESTATE_MONTHLY_STATS,
)

SPATIAL_TABLES: tuple[Table, ...] = tuple(t for t in MANIFEST if t.spatial)

# Quick lookup by name.
BY_NAME: dict[str, Table] = {t.name: t for t in MANIFEST}
