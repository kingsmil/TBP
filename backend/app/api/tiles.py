"""Vector-tile generation via PostGIS ST_AsMVT (production path).

Layers are defined declaratively. Each tile is generated entirely in the
database: clip + project geometry to Web Mercator with ST_AsMVTGeom, then
encode with ST_AsMVT. A small per-layer min_zoom implements crude zoom
generalization (dense layers are hidden when zoomed far out); finer
clustering can be added later.

Returns raw protobuf bytes suitable for Leaflet.VectorGrid / MapLibre.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text


@dataclass(frozen=True)
class LayerDef:
    table: str
    attributes: str           # comma-separated columns to embed in the tile
    min_zoom: int = 0
    where: str = ""           # optional extra filter (e.g. status)


LAYERS: dict[str, LayerDef] = {
    "blocks": LayerDef("hdb_blocks",
                       "block_id, block_number, town, planning_area_id",
                       min_zoom=11),
    "mrt": LayerDef("mrt_stations", "station_id, station_name, line_name",
                    where="status = 'operational'"),
    "future_mrt": LayerDef("mrt_stations", "station_id, station_name, line_name",
                           where="status = 'future'"),
    "bus_stops": LayerDef("bus_stops", "bus_stop_code, description", min_zoom=14),
    "schools": LayerDef("schools", "school_id, school_name, school_type", min_zoom=12),
    "bto": LayerDef("bto_projects", "project_id, project_name, launch_year"),
    "planning_areas": LayerDef("planning_areas", "planning_area_id, name, region"),
}


def _tile_sql(layer: str, ld: LayerDef) -> text:
    extra = f"AND {ld.where}" if ld.where else ""
    return text(f"""
        WITH bounds AS (SELECT ST_TileEnvelope(:z, :x, :y) AS env)
        SELECT ST_AsMVT(mvt, :layer) AS tile FROM (
            SELECT
                ST_AsMVTGeom(
                    ST_Transform(t.geom, 3857),
                    bounds.env, 4096, 64, true
                ) AS geom,
                {ld.attributes}
            FROM {ld.table} t, bounds
            WHERE t.geom && ST_Transform(bounds.env, 4326)
              {extra}
        ) AS mvt
    """)


def build_tile(engine, layer: str, z: int, x: int, y: int) -> bytes:
    """Return MVT bytes for the layer/tile, or empty bytes below min zoom."""
    ld = LAYERS.get(layer)
    if ld is None:
        raise KeyError(f"unknown layer: {layer}")
    if z < ld.min_zoom:
        return b""
    with engine.connect() as conn:
        row = conn.execute(_tile_sql(layer, ld),
                           {"z": z, "x": x, "y": y, "layer": layer}).first()
    return bytes(row.tile) if row and row.tile is not None else b""
