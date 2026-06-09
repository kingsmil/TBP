"""Sync official LTA bus stops and route sequences into PostGIS."""
from __future__ import annotations

import logging
import os

import requests
from sqlalchemy import text

from app.db.session import get_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATAGOV_BUS_STOPS = "d_3f172c6feb3f4f92a2f47d93eed2908a"
DATAGOV_DOWNLOAD = (
    "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
)
DATAMALL_BASE = "https://datamall2.mytransport.sg/ltaodataservice"


def _get_json(url: str, *, headers=None, params=None) -> dict:
    response = requests.get(url, headers=headers, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def fetch_public_bus_stops() -> list[dict]:
    poll = _get_json(DATAGOV_DOWNLOAD.format(dataset_id=DATAGOV_BUS_STOPS))
    geojson = _get_json(poll["data"]["url"])
    rows = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if len(coordinates) < 2:
            continue
        code = str(props.get("BUS_STOP_NUM") or "").zfill(5)
        if code:
            rows.append({
                "code": code,
                "description": f"Bus Stop {code}",
                "lon": float(coordinates[0]),
                "lat": float(coordinates[1]),
            })
    return rows


def fetch_datamall_pages(resource: str, account_key: str) -> list[dict]:
    rows: list[dict] = []
    skip = 0
    headers = {"AccountKey": account_key, "accept": "application/json"}
    while True:
        batch = _get_json(
            f"{DATAMALL_BASE}/{resource}",
            headers=headers,
            params={"$skip": skip},
        ).get("value", [])
        rows.extend(batch)
        log.info("Fetched %d %s rows", len(rows), resource)
        if len(batch) < 500:
            return rows
        skip += 500


def sync(account_key: str | None) -> tuple[int, int]:
    public_stops = fetch_public_bus_stops()
    datamall_stops = fetch_datamall_pages("BusStops", account_key) if account_key else []
    routes = fetch_datamall_pages("BusRoutes", account_key) if account_key else []

    stops = public_stops
    if datamall_stops:
        stops = [{
            "code": row["BusStopCode"],
            "description": row.get("Description") or row.get("RoadName") or row["BusStopCode"],
            "lat": float(row["Latitude"]),
            "lon": float(row["Longitude"]),
        } for row in datamall_stops]

    with get_engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO bus_stops (bus_stop_code, description, geom)
            VALUES (:code, :description, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            ON CONFLICT (bus_stop_code) DO UPDATE SET
                description = EXCLUDED.description,
                geom = EXCLUDED.geom
        """), stops)
        if routes:
            conn.execute(text("TRUNCATE bus_routes"))
            conn.execute(text("""
                INSERT INTO bus_routes
                    (service_no, direction, stop_sequence, bus_stop_code, distance_km)
                VALUES (:service, :direction, :sequence, :stop, :distance)
            """), [{
                "service": row["ServiceNo"],
                "direction": int(row["Direction"]),
                "sequence": int(row["StopSequence"]),
                "stop": row["BusStopCode"],
                "distance": row.get("Distance"),
            } for row in routes])
    return len(stops), len(routes)


def main() -> int:
    key = os.environ.get("LTA_DATAMALL_API_KEY")
    stops, routes = sync(key)
    log.info("Stored %d bus stops and %d route rows", stops, routes)
    if not key:
        log.warning("LTA_DATAMALL_API_KEY is missing; stops loaded, routes unavailable.")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
