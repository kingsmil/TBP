"""PostGIS implementation of the Repository interface.

Production only (needs SQLAlchemy + psycopg + a live PostGIS DB). Reads return
the same domain models the in-memory repo returns, so services are unchanged.

Geospatial-first notes:
  * Points are written as ST_SetSRID(ST_MakePoint(lon, lat), 4326); the
    generated geom_svy21 column is computed by the database.
  * Distance/proximity computation lives in SQL (see refresh_proximity), using
    the GIST-indexed geom_svy21 column and the KNN operator.

For very large datasets the analytics endpoints should read the materialized
views directly rather than pulling rows through here; that is a documented
follow-up optimization, not required for Phase 1 correctness.
"""
from __future__ import annotations

import json
from typing import Iterable, Sequence

from sqlalchemy import text

from app.core.geo import Point
from app.core.models import (
    Block,
    BlockProximity,
    BtoProject,
    BusStop,
    MrtStation,
    PlanningArea,
    School,
    SearchQuery,
    Transaction,
)
from app.repositories.base import Repository


class PostgisRepository(Repository):
    def __init__(self, engine) -> None:
        self._engine = engine

    # --- writes -------------------------------------------------------------
    def add_planning_areas(self, items: Iterable[PlanningArea]) -> None:
        sql = text(
            "INSERT INTO planning_areas (planning_area_id, name, region, geom) "
            "VALUES (:id, :name, :region, ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)) "
            "ON CONFLICT (planning_area_id) DO NOTHING"
        )
        rows = [{
            "id": p.planning_area_id, "name": p.name, "region": p.region,
            "gj": json.dumps({"type": "MultiPolygon",
                              "coordinates": [[ring for ring in p.polygon]]}),
        } for p in items]
        self._exec_many(sql, rows)

    def add_mrt_stations(self, items: Iterable[MrtStation]) -> None:
        sql = text(
            "INSERT INTO mrt_stations (station_id, station_name, line_name, status, opening_year, geom) "
            "VALUES (:id, :name, :line, :status, :year, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) "
            "ON CONFLICT (station_id) DO NOTHING"
        )
        self._exec_many(sql, [{
            "id": m.station_id, "name": m.station_name, "line": m.line_name,
            "status": m.status, "year": m.opening_year,
            "lon": m.point.lon, "lat": m.point.lat,
        } for m in items])

    def add_bus_stops(self, items: Iterable[BusStop]) -> None:
        sql = text(
            "INSERT INTO bus_stops (bus_stop_code, description, geom) "
            "VALUES (:code, :desc, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) "
            "ON CONFLICT (bus_stop_code) DO NOTHING"
        )
        self._exec_many(sql, [{
            "code": b.bus_stop_code, "desc": b.description,
            "lon": b.point.lon, "lat": b.point.lat,
        } for b in items])

    def add_schools(self, items: Iterable[School]) -> None:
        sql = text(
            "INSERT INTO schools (school_id, school_name, school_type, geom) "
            "VALUES (:id, :name, :type, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) "
            "ON CONFLICT (school_id) DO NOTHING"
        )
        self._exec_many(sql, [{
            "id": s.school_id, "name": s.school_name, "type": s.school_type,
            "lon": s.point.lon, "lat": s.point.lat,
        } for s in items])

    def add_bto_projects(self, items: Iterable[BtoProject]) -> None:
        sql = text(
            "INSERT INTO bto_projects (project_id, project_name, launch_year, geom) "
            "VALUES (:id, :name, :year, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) "
            "ON CONFLICT (project_id) DO NOTHING"
        )
        self._exec_many(sql, [{
            "id": p.project_id, "name": p.project_name, "year": p.launch_year,
            "lon": p.point.lon, "lat": p.point.lat,
        } for p in items])

    def add_blocks(self, items: Iterable[Block]) -> None:
        sql = text(
            "INSERT INTO hdb_blocks (block_id, block_number, street_name, postal_code, "
            "town, planning_area_id, lease_commencement_year, geom) "
            "VALUES (:id, :num, :street, :postal, :town, :pa, :lease, "
            "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) "
            "ON CONFLICT (block_id) DO NOTHING"
        )
        self._exec_many(sql, [{
            "id": b.block_id, "num": b.block_number, "street": b.street_name,
            "postal": b.postal_code, "town": b.town, "pa": b.planning_area_id,
            "lease": b.lease_commencement_year,
            "lon": b.point.lon, "lat": b.point.lat,
        } for b in items])

    def add_transactions(self, items: Iterable[Transaction]) -> None:
        sql = text(
            "INSERT INTO hdb_transactions (block_id, transaction_month, resale_price, "
            "floor_area_sqm, flat_type, storey_range) "
            "VALUES (:block, :month, :price, :area, :ft, :storey)"
        )
        self._exec_many(sql, [{
            "block": t.block_id, "month": t.transaction_month,
            "price": t.resale_price, "area": t.floor_area_sqm,
            "ft": t.flat_type, "storey": t.storey_range,
        } for t in items])

    def set_proximity(self, items: Iterable[BlockProximity]) -> None:
        sql = text(
            "INSERT INTO block_proximity (block_id, nearest_mrt_station_id, "
            "nearest_mrt_distance_m, nearest_future_mrt_station_id, "
            "nearest_future_mrt_distance_m, nearest_bus_stop_code, "
            "nearest_bus_distance_m, schools_within_1km, schools_within_2km, "
            "bus_stops_within_400m) VALUES (:id, :mrt, :mrt_d, :fmrt, :fmrt_d, "
            ":bus, :bus_d, :s1, :s2, :b400) "
            "ON CONFLICT (block_id) DO UPDATE SET "
            "nearest_mrt_station_id = EXCLUDED.nearest_mrt_station_id, "
            "nearest_mrt_distance_m = EXCLUDED.nearest_mrt_distance_m, "
            "nearest_future_mrt_station_id = EXCLUDED.nearest_future_mrt_station_id, "
            "nearest_future_mrt_distance_m = EXCLUDED.nearest_future_mrt_distance_m, "
            "nearest_bus_stop_code = EXCLUDED.nearest_bus_stop_code, "
            "nearest_bus_distance_m = EXCLUDED.nearest_bus_distance_m, "
            "schools_within_1km = EXCLUDED.schools_within_1km, "
            "schools_within_2km = EXCLUDED.schools_within_2km, "
            "bus_stops_within_400m = EXCLUDED.bus_stops_within_400m"
        )
        self._exec_many(sql, [{
            "id": p.block_id, "mrt": p.nearest_mrt_station_id,
            "mrt_d": p.nearest_mrt_distance_m,
            "fmrt": p.nearest_future_mrt_station_id,
            "fmrt_d": p.nearest_future_mrt_distance_m,
            "bus": p.nearest_bus_stop_code, "bus_d": p.nearest_bus_distance_m,
            "s1": p.schools_within_1km, "s2": p.schools_within_2km,
            "b400": p.bus_stops_within_400m,
        } for p in items])

    # --- reads --------------------------------------------------------------
    def planning_areas(self) -> Sequence[PlanningArea]:
        rows = self._all("SELECT planning_area_id, name, region FROM planning_areas")
        return [PlanningArea(r.planning_area_id, r.name, r.region, []) for r in rows]

    def mrt_stations(self, status: str | None = None) -> Sequence[MrtStation]:
        q = ("SELECT station_id, station_name, line_name, status, opening_year, "
             "ST_X(geom) lon, ST_Y(geom) lat FROM mrt_stations")
        params = {}
        if status is not None:
            q += " WHERE status = :status"
            params["status"] = status
        return [MrtStation(r.station_id, r.station_name, r.line_name, r.status,
                           r.opening_year, Point(r.lon, r.lat))
                for r in self._all(q, params)]

    def bus_stops(self) -> Sequence[BusStop]:
        rows = self._all("SELECT bus_stop_code, description, ST_X(geom) lon, "
                         "ST_Y(geom) lat FROM bus_stops")
        return [BusStop(r.bus_stop_code, r.description, Point(r.lon, r.lat)) for r in rows]

    def schools(self) -> Sequence[School]:
        rows = self._all("SELECT school_id, school_name, school_type, "
                         "ST_X(geom) lon, ST_Y(geom) lat FROM schools")
        return [School(r.school_id, r.school_name, r.school_type, Point(r.lon, r.lat))
                for r in rows]

    def bto_projects(self) -> Sequence[BtoProject]:
        rows = self._all("SELECT project_id, project_name, launch_year, "
                         "ST_X(geom) lon, ST_Y(geom) lat FROM bto_projects")
        return [BtoProject(r.project_id, r.project_name, r.launch_year,
                           Point(r.lon, r.lat)) for r in rows]

    def blocks(self) -> Sequence[Block]:
        return [self._block_row(r) for r in self._all(self._BLOCK_SELECT)]

    def block(self, block_id: int) -> Block | None:
        rows = self._all(self._BLOCK_SELECT + " WHERE block_id = :id", {"id": block_id})
        return self._block_row(rows[0]) if rows else None

    def transactions(self) -> Sequence[Transaction]:
        return [self._txn_row(r) for r in self._all(self._TXN_SELECT)]

    def transactions_for_block(self, block_id: int) -> Sequence[Transaction]:
        rows = self._all(self._TXN_SELECT + " WHERE block_id = :id", {"id": block_id})
        return [self._txn_row(r) for r in rows]

    def proximity(self, block_id: int) -> BlockProximity | None:
        rows = self._all("SELECT * FROM block_proximity WHERE block_id = :id",
                         {"id": block_id})
        if not rows:
            return None
        r = rows[0]
        return BlockProximity(
            block_id=r.block_id,
            nearest_mrt_station_id=r.nearest_mrt_station_id,
            nearest_mrt_distance_m=float(r.nearest_mrt_distance_m) if r.nearest_mrt_distance_m is not None else None,
            nearest_future_mrt_station_id=r.nearest_future_mrt_station_id,
            nearest_future_mrt_distance_m=float(r.nearest_future_mrt_distance_m) if r.nearest_future_mrt_distance_m is not None else None,
            nearest_bus_stop_code=r.nearest_bus_stop_code,
            nearest_bus_distance_m=float(r.nearest_bus_distance_m) if r.nearest_bus_distance_m is not None else None,
            schools_within_1km=r.schools_within_1km or 0,
            schools_within_2km=r.schools_within_2km or 0,
            bus_stops_within_400m=r.bus_stops_within_400m or 0,
        )

    def search_blocks(self, q: SearchQuery) -> list[dict]:
        """Execute the map search as one aggregate SQL query."""
        txn_where: list[str] = []
        block_where: list[str] = []
        stats_where: list[str] = []
        params: dict = {"limit": q.limit}

        def add(clauses, sql, name, value):
            if value is not None:
                clauses.append(sql)
                params[name] = value

        add(txn_where, "flat_type = :flat_type", "flat_type", q.flat_type)
        add(txn_where, "floor_area_sqm >= :min_floor_area", "min_floor_area", q.min_floor_area)
        add(txn_where, "floor_area_sqm <= :max_floor_area", "max_floor_area", q.max_floor_area)
        add(block_where, "b.town = :town", "town", q.town)
        add(block_where, "b.planning_area_id = :planning_area_id", "planning_area_id", q.planning_area_id)
        add(block_where, "b.lease_commencement_year >= :min_lease_year", "min_lease_year", q.min_lease_year)
        add(block_where, "b.lease_commencement_year <= :max_lease_year", "max_lease_year", q.max_lease_year)
        add(block_where, "p.nearest_mrt_distance_m <= :max_mrt_distance_m", "max_mrt_distance_m", q.max_mrt_distance_m)
        add(block_where, "p.nearest_bus_distance_m <= :max_bus_distance_m", "max_bus_distance_m", q.max_bus_distance_m)
        add(block_where, "p.schools_within_1km >= :min_schools", "min_schools", q.min_schools_within_1km)
        add(stats_where, "s.median_price >= :min_price", "min_price", q.min_price)
        add(stats_where, "s.median_price <= :max_price", "max_price", q.max_price)
        add(stats_where, "s.median_psf >= :min_psf", "min_psf", q.min_psf)
        add(stats_where, "s.median_psf <= :max_psf", "max_psf", q.max_psf)

        if q.bbox is not None:
            minx, miny, maxx, maxy = q.bbox
            block_where.append(
                "b.geom && ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326)"
            )
            params.update(minx=minx, miny=miny, maxx=maxx, maxy=maxy)

        requires_stats = any(v is not None for v in (
            q.flat_type, q.min_floor_area, q.max_floor_area,
            q.min_price, q.max_price, q.min_psf, q.max_psf,
        ))
        join = "JOIN" if requires_stats else "LEFT JOIN"
        txn_predicate = "WHERE " + " AND ".join(txn_where) if txn_where else ""
        predicates = block_where + stats_where
        final_where = "WHERE " + " AND ".join(predicates) if predicates else ""

        sql = text(f"""
            WITH stats AS (
                SELECT block_id,
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY psf) AS median_psf,
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY resale_price) AS median_price,
                    count(*) AS txn_count
                FROM hdb_transactions
                {txn_predicate}
                GROUP BY block_id
            )
            SELECT b.block_id, b.block_number, b.street_name, b.town,
                b.planning_area_id, ST_X(b.geom) AS lon, ST_Y(b.geom) AS lat,
                b.lease_commencement_year, p.nearest_mrt_distance_m,
                p.schools_within_1km, s.median_psf, s.median_price,
                COALESCE(s.txn_count, 0) AS txn_count
            FROM hdb_blocks b
            LEFT JOIN block_proximity p ON p.block_id = b.block_id
            {join} stats s ON s.block_id = b.block_id
            {final_where}
            ORDER BY s.median_psf ASC NULLS LAST, b.block_id ASC
            LIMIT :limit
        """)
        with self._engine.connect() as conn:
            rows = conn.execute(sql, params).mappings().all()
        return [{
            **dict(row),
            "nearest_mrt_distance_m": (
                float(row["nearest_mrt_distance_m"])
                if row["nearest_mrt_distance_m"] is not None else None
            ),
            "median_psf": (
                round(float(row["median_psf"]), 2)
                if row["median_psf"] is not None else None
            ),
            "median_price": (
                round(float(row["median_price"]), 2)
                if row["median_price"] is not None else None
            ),
        } for row in rows]

    def bus_stop_reach(self, bus_stop_code: str) -> dict | None:
        origin_rows = self._all(
            "SELECT bus_stop_code, description, ST_X(geom) lon, ST_Y(geom) lat "
            "FROM bus_stops WHERE bus_stop_code = :code",
            {"code": bus_stop_code},
        )
        if not origin_rows:
            return None
        origin = origin_rows[0]
        rows = self._all("""
            WITH origins AS (
                SELECT service_no, direction, min(stop_sequence) AS stop_sequence
                FROM bus_routes
                WHERE bus_stop_code = :code
                GROUP BY service_no, direction
            )
            SELECT r.service_no, r.direction, r.stop_sequence,
                s.bus_stop_code, s.description,
                ST_X(s.geom) AS lon, ST_Y(s.geom) AS lat
            FROM origins o
            JOIN bus_routes r
              ON r.service_no = o.service_no
             AND r.direction = o.direction
             AND r.stop_sequence >= o.stop_sequence
            JOIN bus_stops s ON s.bus_stop_code = r.bus_stop_code
            ORDER BY r.service_no, r.direction, r.stop_sequence
        """, {"code": bus_stop_code})
        services: list[dict] = []
        current_key = None
        current = None
        reachable: dict[str, dict] = {}
        for row in rows:
            key = (row.service_no, row.direction)
            if key != current_key:
                current = {
                    "service_no": row.service_no,
                    "direction": row.direction,
                    "stops": [],
                }
                services.append(current)
                current_key = key
            stop = {
                "bus_stop_code": row.bus_stop_code,
                "description": row.description,
                "lat": float(row.lat),
                "lon": float(row.lon),
                "stop_sequence": row.stop_sequence,
            }
            current["stops"].append(stop)
            if row.bus_stop_code != bus_stop_code:
                reachable[row.bus_stop_code] = stop
        return {
            "origin": {
                "bus_stop_code": origin.bus_stop_code,
                "description": origin.description,
                "lat": float(origin.lat),
                "lon": float(origin.lon),
            },
            "service_count": len(services),
            "reachable_stop_count": len(reachable),
            "services": services,
            "reachable_stops": list(reachable.values()),
        }

    def direct_transit_convenience(
        self,
        destinations: list[dict],
        *,
        max_walk_m: float,
        modes: list[str],
        limit: int,
        property_filters: dict | None = None,
    ) -> dict:
        property_filters = property_filters or {}
        per_destination: list[dict[int, list[dict]]] = []
        for destination in destinations:
            params = {
                "lat": destination["lat"],
                "lon": destination["lon"],
                "walk": max_walk_m,
            }
            parts: list[str] = []
            if "bus" in modes:
                parts.append("""
                    SELECT b.block_id, 'bus' AS mode,
                        origin.bus_stop_code AS origin_code,
                        origin.description AS origin_name,
                        destination_stop.bus_stop_code AS destination_code,
                        destination_stop.description AS destination_name,
                        routes.service_no AS service,
                        routes.direction::text AS direction,
                        ST_Distance(b.geom_svy21, origin.geom_svy21) AS origin_walk_m,
                        ST_Distance(destination_stop.geom_svy21, point.geom) AS destination_walk_m
                    FROM destination_point point
                    JOIN bus_stops destination_stop
                      ON ST_DWithin(destination_stop.geom_svy21, point.geom, :walk)
                    JOIN bus_routes destination_route
                      ON destination_route.bus_stop_code = destination_stop.bus_stop_code
                    JOIN bus_routes routes
                      ON routes.service_no = destination_route.service_no
                     AND routes.direction = destination_route.direction
                     AND routes.stop_sequence <= destination_route.stop_sequence
                    JOIN bus_stops origin ON origin.bus_stop_code = routes.bus_stop_code
                    JOIN hdb_blocks b ON ST_DWithin(b.geom_svy21, origin.geom_svy21, :walk)
                """)
            if "mrt" in modes:
                parts.append("""
                    SELECT b.block_id, 'mrt' AS mode,
                        origin.station_id::text AS origin_code,
                        origin.station_name AS origin_name,
                        destination_station.station_id::text AS destination_code,
                        destination_station.station_name AS destination_name,
                        origin.line_name AS service,
                        NULL::text AS direction,
                        ST_Distance(b.geom_svy21, origin.geom_svy21) AS origin_walk_m,
                        ST_Distance(destination_station.geom_svy21, point.geom) AS destination_walk_m
                    FROM destination_point point
                    JOIN mrt_stations destination_station
                      ON destination_station.status = 'operational'
                     AND ST_DWithin(destination_station.geom_svy21, point.geom, :walk)
                    JOIN mrt_stations origin
                      ON origin.status = 'operational'
                     AND origin.line_name = destination_station.line_name
                    JOIN hdb_blocks b ON ST_DWithin(b.geom_svy21, origin.geom_svy21, :walk)
                """)
            sql = text("""
                WITH destination_point AS (
                    SELECT ST_Transform(
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 3414
                    ) AS geom
                ), matches AS (
            """ + " UNION ALL ".join(parts) + """
                ), ranked AS (
                    SELECT *, row_number() OVER (
                        PARTITION BY block_id, mode
                        ORDER BY origin_walk_m + destination_walk_m
                    ) AS rank
                    FROM matches
                )
                SELECT * FROM ranked WHERE rank = 1
            """)
            with self._engine.connect() as conn:
                rows = conn.execute(sql, params).mappings().all()
            matches: dict[int, list[dict]] = {}
            for row in rows:
                matches.setdefault(row["block_id"], []).append({
                    "mode": row["mode"],
                    "origin_code": row["origin_code"],
                    "origin_name": row["origin_name"],
                    "destination_code": row["destination_code"],
                    "destination_name": row["destination_name"],
                    "service": row["service"],
                    "direction": row["direction"],
                    "origin_walk_m": round(float(row["origin_walk_m"]), 1),
                    "destination_walk_m": round(float(row["destination_walk_m"]), 1),
                })
            per_destination.append(matches)

        matching_ids = set(per_destination[0])
        for matches in per_destination[1:]:
            matching_ids.intersection_update(matches)
        if not matching_ids:
            return {
                "count": 0,
                "walk_limit_m": max_walk_m,
                "destinations": destinations,
                "results": [],
            }

        ids = sorted(matching_ids)
        txn_where: list[str] = ["block_id = ANY(:ids)"]
        block_where: list[str] = ["b.block_id = ANY(:ids)"]
        stats_where: list[str] = []
        summary_params: dict = {"ids": ids, "limit": limit}

        def add(clauses, sql, name):
            value = property_filters.get(name)
            if value is not None:
                clauses.append(sql)
                summary_params[name] = value

        add(txn_where, "flat_type = :flat_type", "flat_type")
        add(block_where, "b.town = :town", "town")
        add(block_where, "b.planning_area_id = :planning_area_id", "planning_area_id")
        add(block_where, "p.nearest_mrt_distance_m <= :max_mrt_distance_m", "max_mrt_distance_m")
        add(block_where, "p.schools_within_1km >= :min_schools_within_1km", "min_schools_within_1km")
        add(stats_where, "s.median_price >= :min_price", "min_price")
        add(stats_where, "s.median_price <= :max_price", "max_price")
        add(stats_where, "s.median_psf >= :min_psf", "min_psf")
        add(stats_where, "s.median_psf <= :max_psf", "max_psf")
        requires_stats = any(property_filters.get(key) is not None for key in (
            "flat_type", "min_price", "max_price", "min_psf", "max_psf",
        ))
        stats_join = "JOIN" if requires_stats else "LEFT JOIN"
        final_where = " AND ".join(block_where + stats_where)

        summary_sql = text(f"""
            WITH stats AS (
                SELECT block_id,
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY psf) AS median_psf,
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY resale_price) AS median_price,
                    count(*) AS txn_count
                FROM hdb_transactions
                WHERE {" AND ".join(txn_where)}
                GROUP BY block_id
            )
            SELECT b.block_id, b.block_number, b.street_name, b.town,
                b.planning_area_id, ST_X(b.geom) AS lon, ST_Y(b.geom) AS lat,
                b.lease_commencement_year, p.nearest_mrt_distance_m,
                p.schools_within_1km, s.median_psf, s.median_price,
                COALESCE(s.txn_count, 0) AS txn_count
            FROM hdb_blocks b
            LEFT JOIN block_proximity p ON p.block_id = b.block_id
            {stats_join} stats s ON s.block_id = b.block_id
            WHERE {final_where}
            ORDER BY s.median_psf ASC NULLS LAST, b.block_id
            LIMIT :limit
        """)
        with self._engine.connect() as conn:
            rows = conn.execute(summary_sql, summary_params).mappings().all()
        results = []
        for row in rows:
            summary = dict(row)
            for key in ("nearest_mrt_distance_m", "median_psf", "median_price"):
                if summary[key] is not None:
                    summary[key] = round(float(summary[key]), 2)
            summary["transit_matches"] = [
                {
                    "destination": destinations[index]["name"],
                    "options": matches[row["block_id"]],
                }
                for index, matches in enumerate(per_destination)
            ]
            results.append(summary)
        return {
            "count": len(results),
            "walk_limit_m": max_walk_m,
            "destinations": destinations,
            "results": results,
        }

    # --- helpers ------------------------------------------------------------
    _BLOCK_SELECT = (
        "SELECT block_id, block_number, street_name, postal_code, town, "
        "planning_area_id, lease_commencement_year, ST_X(geom) lon, ST_Y(geom) lat "
        "FROM hdb_blocks")
    _TXN_SELECT = (
        "SELECT transaction_id, block_id, to_char(transaction_month,'YYYY-MM-DD') tmonth, "
        "resale_price, floor_area_sqm, flat_type, storey_range FROM hdb_transactions")

    @staticmethod
    def _block_row(r) -> Block:
        return Block(r.block_id, r.block_number, r.street_name, r.postal_code,
                     r.town, r.planning_area_id, r.lease_commencement_year,
                     Point(r.lon, r.lat))

    @staticmethod
    def _txn_row(r) -> Transaction:
        return Transaction(r.transaction_id, r.block_id, r.tmonth,
                           float(r.resale_price), float(r.floor_area_sqm),
                           r.flat_type, r.storey_range)

    def _all(self, sql: str, params: dict | None = None):
        with self._engine.connect() as conn:
            return conn.execute(text(sql), params or {}).all()

    def _exec_many(self, sql, rows: list[dict]) -> None:
        if not rows:
            return
        with self._engine.begin() as conn:
            conn.execute(sql, rows)
