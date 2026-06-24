"""Live data fetcher for HDB Match.

Pulls real data from public APIs and returns a Dataset ready for ingest().

Sources:
  - HDB Resale Prices    → data.gov.sg (no auth)
  - Block geocoding      → OneMap Search API (ONEMAP_TOKEN)
  - Schools              → data.gov.sg (no auth)
  - MRT stations         → curated static list (reliable, infrequently changes)
  - Planning areas       → derived from town name groups + block centroids
  - Bus stops            → skipped (LTA DataMall requires separate registration)

Usage:
  python -m app.data.seed_live          # ingest into PostGIS
"""
from __future__ import annotations

import logging
import csv
import io
import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import requests

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
from app.data.mock import Dataset

log = logging.getLogger(__name__)

# data.gov.sg HDB Resale resource (2017–present)
HDB_RESOURCE_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
DATAGOV_URL = "https://data.gov.sg/api/action/datastore_search"
DATAGOV_DOWNLOAD_URL = (
    "https://api-open.data.gov.sg/v1/public/api/datasets/"
    "{resource_id}/poll-download"
)
ONEMAP_SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
GEOCODE_CACHE_PATH = Path(__file__).parent / "generated" / "onemap_geocodes.json"

# ── Static MRT station list ───────────────────────────────────────────────────
# Curated set: station_id, name, line, status, opening_year, lat, lon
_MRT_STATIONS: list[tuple] = [
    # EW Line
    (1,  "Pasir Ris",        "EW", "operational", None, 1.3731, 103.9494),
    (2,  "Tampines",         "EW", "operational", None, 1.3529, 103.9453),
    (3,  "Simei",            "EW", "operational", None, 1.3431, 103.9530),
    (4,  "Tanah Merah",      "EW", "operational", None, 1.3274, 103.9461),
    (5,  "Bedok",            "EW", "operational", None, 1.3240, 103.9299),
    (6,  "Kembangan",        "EW", "operational", None, 1.3210, 103.9131),
    (7,  "Eunos",            "EW", "operational", None, 1.3196, 103.9028),
    (8,  "Paya Lebar",       "EW", "operational", None, 1.3179, 103.8925),
    (9,  "Aljunied",         "EW", "operational", None, 1.3162, 103.8827),
    (10, "Kallang",          "EW", "operational", None, 1.3113, 103.8713),
    (11, "Lavender",         "EW", "operational", None, 1.3073, 103.8631),
    (12, "City Hall",        "EW", "operational", None, 1.2931, 103.8520),
    (13, "Raffles Place",    "EW", "operational", None, 1.2840, 103.8514),
    (14, "Tanjong Pagar",    "EW", "operational", None, 1.2764, 103.8454),
    (15, "Outram Park",      "EW", "operational", None, 1.2801, 103.8395),
    (16, "Tiong Bahru",      "EW", "operational", None, 1.2862, 103.8276),
    (17, "Redhill",          "EW", "operational", None, 1.2895, 103.8167),
    (18, "Queenstown",       "EW", "operational", None, 1.2942, 103.8062),
    (19, "Commonwealth",     "EW", "operational", None, 1.3022, 103.7981),
    (20, "Buona Vista",      "EW", "operational", None, 1.3071, 103.7900),
    (21, "Dover",            "EW", "operational", None, 1.3113, 103.7787),
    (22, "Clementi",         "EW", "operational", None, 1.3152, 103.7650),
    (23, "Jurong East",      "EW", "operational", None, 1.3333, 103.7422),
    (24, "Chinese Garden",   "EW", "operational", None, 1.3424, 103.7321),
    (25, "Lakeside",         "EW", "operational", None, 1.3441, 103.7211),
    (26, "Boon Lay",         "EW", "operational", None, 1.3386, 103.7059),
    (27, "Pioneer",          "EW", "operational", None, 1.3375, 103.6975),
    (28, "Joo Koon",         "EW", "operational", None, 1.3278, 103.6786),
    # NS Line
    (29, "Jurong East",      "NS", "operational", None, 1.3333, 103.7422),
    (30, "Bukit Batok",      "NS", "operational", None, 1.3490, 103.7494),
    (31, "Bukit Gombak",     "NS", "operational", None, 1.3588, 103.7517),
    (32, "Choa Chu Kang",    "NS", "operational", None, 1.3854, 103.7448),
    (33, "Yew Tee",          "NS", "operational", None, 1.3970, 103.7475),
    (34, "Kranji",           "NS", "operational", None, 1.4252, 103.7619),
    (35, "Marsiling",        "NS", "operational", None, 1.4326, 103.7743),
    (36, "Woodlands",        "NS", "operational", None, 1.4369, 103.7864),
    (37, "Admiralty",        "NS", "operational", None, 1.4407, 103.8006),
    (38, "Sembawang",        "NS", "operational", None, 1.4491, 103.8202),
    (39, "Yishun",           "NS", "operational", None, 1.4294, 103.8354),
    (40, "Khatib",           "NS", "operational", None, 1.4174, 103.8330),
    (41, "Yio Chu Kang",     "NS", "operational", None, 1.3817, 103.8449),
    (42, "Ang Mo Kio",       "NS", "operational", None, 1.3700, 103.8497),
    (43, "Bishan",           "NS", "operational", None, 1.3510, 103.8490),
    (44, "Braddell",         "NS", "operational", None, 1.3402, 103.8469),
    (45, "Toa Payoh",        "NS", "operational", None, 1.3328, 103.8471),
    (46, "Novena",           "NS", "operational", None, 1.3203, 103.8437),
    (47, "Newton",           "NS", "operational", None, 1.3121, 103.8384),
    (48, "Orchard",          "NS", "operational", None, 1.3042, 103.8319),
    (49, "Somerset",         "NS", "operational", None, 1.2999, 103.8389),
    (50, "Dhoby Ghaut",      "NS", "operational", None, 1.2991, 103.8455),
    # NE Line
    (51, "HarbourFront",     "NE", "operational", None, 1.2654, 103.8218),
    (52, "Outram Park",      "NE", "operational", None, 1.2801, 103.8395),
    (53, "Chinatown",        "NE", "operational", None, 1.2843, 103.8438),
    (54, "Clarke Quay",      "NE", "operational", None, 1.2882, 103.8465),
    (55, "Dhoby Ghaut",      "NE", "operational", None, 1.2991, 103.8455),
    (56, "Little India",     "NE", "operational", None, 1.3066, 103.8494),
    (57, "Farrer Park",      "NE", "operational", None, 1.3122, 103.8540),
    (58, "Boon Keng",        "NE", "operational", None, 1.3193, 103.8617),
    (59, "Potong Pasir",     "NE", "operational", None, 1.3316, 103.8695),
    (60, "Woodleigh",        "NE", "operational", None, 1.3393, 103.8706),
    (61, "Serangoon",        "NE", "operational", None, 1.3498, 103.8732),
    (62, "Kovan",            "NE", "operational", None, 1.3598, 103.8854),
    (63, "Hougang",          "NE", "operational", None, 1.3712, 103.8924),
    (64, "Buangkok",         "NE", "operational", None, 1.3829, 103.8929),
    (65, "Sengkang",         "NE", "operational", None, 1.3915, 103.8954),
    (66, "Punggol",          "NE", "operational", None, 1.4052, 103.9022),
    # CC Line
    (67, "Dhoby Ghaut",      "CC", "operational", None, 1.2991, 103.8455),
    (68, "Bras Basah",       "CC", "operational", None, 1.2966, 103.8504),
    (69, "Esplanade",        "CC", "operational", None, 1.2934, 103.8556),
    (70, "Promenade",        "CC", "operational", None, 1.2933, 103.8609),
    (71, "Nicoll Highway",   "CC", "operational", None, 1.2999, 103.8637),
    (72, "Stadium",          "CC", "operational", None, 1.3026, 103.8749),
    (73, "Mountbatten",      "CC", "operational", None, 1.3064, 103.8821),
    (74, "Dakota",           "CC", "operational", None, 1.3084, 103.8885),
    (75, "Paya Lebar",       "CC", "operational", None, 1.3179, 103.8925),
    (76, "MacPherson",       "CC", "operational", None, 1.3266, 103.8897),
    (77, "Tai Seng",         "CC", "operational", None, 1.3354, 103.8880),
    (78, "Bartley",          "CC", "operational", None, 1.3425, 103.8796),
    (79, "Serangoon",        "CC", "operational", None, 1.3498, 103.8732),
    (80, "Lorong Chuan",     "CC", "operational", None, 1.3516, 103.8651),
    (81, "Bishan",           "CC", "operational", None, 1.3510, 103.8490),
    (82, "Marymount",        "CC", "operational", None, 1.3469, 103.8393),
    (83, "Caldecott",        "CC", "operational", None, 1.3376, 103.8393),
    (84, "Botanic Gardens",  "CC", "operational", None, 1.3224, 103.8155),
    (85, "Farrer Road",      "CC", "operational", None, 1.3174, 103.8075),
    (86, "Holland Village",  "CC", "operational", None, 1.3116, 103.7964),
    (87, "Buona Vista",      "CC", "operational", None, 1.3071, 103.7900),
    (88, "one-north",        "CC", "operational", None, 1.2997, 103.7870),
    (89, "Kent Ridge",       "CC", "operational", None, 1.2930, 103.7845),
    (90, "Haw Par Villa",    "CC", "operational", None, 1.2823, 103.7820),
    (91, "Pasir Panjang",    "CC", "operational", None, 1.2762, 103.7917),
    (92, "Labrador Park",    "CC", "operational", None, 1.2726, 103.8024),
    (93, "Telok Blangah",    "CC", "operational", None, 1.2704, 103.8094),
    (94, "HarbourFront",     "CC", "operational", None, 1.2654, 103.8218),
    # DT Line
    (95, "Bukit Panjang",    "DT", "operational", None, 1.3791, 103.7637),
    (96, "Cashew",           "DT", "operational", None, 1.3696, 103.7758),
    (97, "Hillview",         "DT", "operational", None, 1.3626, 103.7677),
    (98, "Beauty World",     "DT", "operational", None, 1.3411, 103.7756),
    (99, "King Albert Park", "DT", "operational", None, 1.3353, 103.7829),
    (100,"Sixth Avenue",     "DT", "operational", None, 1.3303, 103.7978),
    (101,"Tan Kah Kee",      "DT", "operational", None, 1.3254, 103.8076),
    (102,"Botanic Gardens",  "DT", "operational", None, 1.3224, 103.8155),
    (103,"Stevens",          "DT", "operational", None, 1.3200, 103.8260),
    (104,"Newton",           "DT", "operational", None, 1.3121, 103.8384),
    (105,"Little India",     "DT", "operational", None, 1.3066, 103.8494),
    (106,"Rochor",           "DT", "operational", None, 1.3035, 103.8527),
    (107,"Bugis",            "DT", "operational", None, 1.3009, 103.8565),
    (108,"Promenade",        "DT", "operational", None, 1.2933, 103.8609),
    (109,"Bayfront",         "DT", "operational", None, 1.2822, 103.8597),
    (110,"Downtown",         "DT", "operational", None, 1.2795, 103.8529),
    (111,"Telok Ayer",       "DT", "operational", None, 1.2821, 103.8481),
    (112,"Chinatown",        "DT", "operational", None, 1.2843, 103.8438),
    (113,"Fort Canning",     "DT", "operational", None, 1.2918, 103.8443),
    (114,"Bencoolen",        "DT", "operational", None, 1.2981, 103.8500),
    (115,"Jln Besar",        "DT", "operational", None, 1.3054, 103.8558),
    (116,"Bendemeer",        "DT", "operational", None, 1.3139, 103.8629),
    (117,"Geylang Bahru",    "DT", "operational", None, 1.3219, 103.8718),
    (118,"Mattar",           "DT", "operational", None, 1.3268, 103.8831),
    (119,"MacPherson",       "DT", "operational", None, 1.3266, 103.8897),
    (120,"Ubi",              "DT", "operational", None, 1.3299, 103.8990),
    (121,"Kaki Bukit",       "DT", "operational", None, 1.3340, 103.9091),
    (122,"Bedok North",      "DT", "operational", None, 1.3345, 103.9195),
    (123,"Bedok Reservoir",  "DT", "operational", None, 1.3358, 103.9319),
    (124,"Tampines West",    "DT", "operational", None, 1.3456, 103.9380),
    (125,"Tampines",         "DT", "operational", None, 1.3529, 103.9453),
    (126,"Tampines East",    "DT", "operational", None, 1.3576, 103.9535),
    (127,"Upper Changi",     "DT", "operational", None, 1.3415, 103.9613),
    (128,"Expo",             "DT", "operational", None, 1.3353, 103.9613),
    # TE Line (Thomson-East Coast)
    (129,"Woodlands North",  "TE", "operational", 2021, 1.4477, 103.8275),
    (130,"Woodlands",        "TE", "operational", 2021, 1.4369, 103.7864),
    (131,"Woodlands South",  "TE", "operational", 2021, 1.4243, 103.7955),
    (132,"Springleaf",       "TE", "operational", 2021, 1.3997, 103.8194),
    (133,"Lentor",           "TE", "operational", 2021, 1.3877, 103.8357),
    (134,"Mayflower",        "TE", "operational", 2021, 1.3795, 103.8395),
    (135,"Bright Hill",      "TE", "operational", 2022, 1.3692, 103.8344),
    (136,"Upper Thomson",    "TE", "operational", 2022, 1.3564, 103.8307),
    (137,"Caldecott",        "TE", "operational", 2022, 1.3376, 103.8393),
    (138,"Stevens",          "TE", "operational", 2022, 1.3200, 103.8260),
    (139,"Napier",           "TE", "operational", 2022, 1.3062, 103.8192),
    (140,"Orchard Boulevard","TE", "operational", 2022, 1.3014, 103.8223),
    (141,"Orchard",          "TE", "operational", 2022, 1.3042, 103.8319),
    (142,"Great World",      "TE", "operational", 2022, 1.2942, 103.8239),
    (143,"Havelock",         "TE", "operational", 2022, 1.2882, 103.8370),
    (144,"Outram Park",      "TE", "operational", 2022, 1.2801, 103.8395),
    (145,"Maxwell",          "TE", "operational", 2023, 1.2794, 103.8449),
    (146,"Shenton Way",      "TE", "operational", 2023, 1.2775, 103.8478),
    (147,"Marina Bay",       "TE", "operational", 2023, 1.2762, 103.8548),
    (148,"Marina South",     "TE", "operational", 2023, 1.2726, 103.8612),
    # Future stations (Jurong Region Line)
    (200,"Jurong Lake District","JR","future",    2027, 1.3302, 103.7405),
    (201,"Jurong Town Hall",    "JR","future",    2027, 1.3350, 103.7367),
    (202,"Bahar Junction",      "JR","future",    2028, 1.3538, 103.7175),
    (203,"Tawas",               "JR","future",    2028, 1.3629, 103.7074),
]


# ── Data.gov.sg helpers ───────────────────────────────────────────────────────

def _datagov_fetch_all(resource_id: str, limit: int = 1000,
                        filters: dict | None = None,
                        page_delay: float = 1.0,
                        api_key: str | None = None,
                        sort: str | None = None,
                        stop_when: Callable[[list[dict]], bool] | None = None) -> list[dict]:
    """Page through a data.gov.sg datastore resource and return all records."""
    records: list[dict] = []
    offset = 0
    headers = {"x-api-key": api_key} if api_key else {}
    while True:
        params: dict = {"resource_id": resource_id, "limit": limit, "offset": offset}
        if filters:
            import json as _json
            params["filters"] = _json.dumps(filters)
        if sort:
            params["sort"] = sort

        # Retry up to 5 times with exponential backoff on 429/5xx
        for attempt in range(5):
            resp = requests.get(DATAGOV_URL, params=params, headers=headers, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = 2 ** attempt * 2  # 2, 4, 8, 16, 32 s
                log.warning("HTTP %d at offset %d — retrying in %ds (attempt %d/5)",
                            resp.status_code, offset, wait, attempt + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        else:
            resp.raise_for_status()  # all retries exhausted

        result = resp.json().get("result", {})
        batch = result.get("records", [])
        records.extend(batch)
        log.debug("fetched %d/%d records", len(records), result.get("total", "?"))
        if len(batch) < limit or (stop_when is not None and stop_when(batch)):
            break
        offset += limit
        time.sleep(page_delay)  # be polite between pages
    return records


# ── HDB Transactions ──────────────────────────────────────────────────────────

def fetch_hdb_transactions(months: int = 24, api_key: str | None = None) -> list[dict]:
    """Return raw HDB resale records for the last `months` months."""
    import datetime
    cutoff = (datetime.date.today().replace(day=1)
              - datetime.timedelta(days=months * 30))
    cutoff_str = cutoff.strftime("%Y-%m")
    log.info("Fetching HDB transactions from %s onwards…", cutoff_str)
    headers = {"x-api-key": api_key} if api_key else {}
    try:
        poll = requests.get(
            DATAGOV_DOWNLOAD_URL.format(resource_id=HDB_RESOURCE_ID),
            headers=headers,
            timeout=30,
        )
        poll.raise_for_status()
        download_url = poll.json()["data"]["url"]
        response = requests.get(download_url, timeout=60)
        response.raise_for_status()
        records = list(csv.DictReader(io.StringIO(response.text)))
    except Exception as exc:
        log.warning("CSV download failed (%s); falling back to paginated API", exc)
        records = _datagov_fetch_all(
            HDB_RESOURCE_ID,
            limit=1000,
            page_delay=0.0 if api_key else 1.0,
            api_key=api_key,
            sort="month desc",
            stop_when=lambda batch: (
                bool(batch) and batch[-1].get("month", "") < cutoff_str
            ),
        )
    filtered = [r for r in records if r.get("month", "") >= cutoff_str]
    log.info("  %d transactions after date filter", len(filtered))
    return filtered


# ── OneMap geocoding ──────────────────────────────────────────────────────────

def _geocode_one(search_val: str, token: str) -> tuple[float, float] | None:
    """Return (lat, lon) for a search string, or None if not found."""
    for attempt in range(5):
        try:
            resp = requests.get(
                ONEMAP_SEARCH_URL,
                params={
                    "searchVal": search_val,
                    "returnGeom": "Y",
                    "getAddrDetails": "N",
                },
                headers={"Authorization": token},
                timeout=10,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            body = resp.json()
            if body.get("error"):
                log.warning("OneMap rejected %r: %s", search_val, body["error"])
                return None
            results = body.get("results", [])
            if results:
                r = results[0]
                return float(r["LATITUDE"]), float(r["LONGITUDE"])
            return None
        except requests.RequestException as exc:
            if attempt == 4:
                log.warning("Geocode failed for %r: %s", search_val, exc)
            else:
                time.sleep(2 ** attempt)
    return None


def geocode_blocks(
    unique_addresses: list[tuple[str, str]],  # [(block_no, street_name), ...]
    token: str,
    workers: int = 8,
) -> dict[tuple[str, str], tuple[float, float]]:
    """Geocode unique (block, street) pairs. Returns {(block, street): (lat, lon)}."""
    cache: dict[str, list[float]] = {}
    if GEOCODE_CACHE_PATH.exists():
        try:
            cache = json.loads(GEOCODE_CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("Ignoring invalid geocode cache at %s", GEOCODE_CACHE_PATH)

    results: dict[tuple[str, str], tuple[float, float]] = {}
    pending: list[tuple[str, str]] = []
    for address in unique_addresses:
        key = "|".join(address)
        if key in cache:
            results[address] = tuple(cache[key])
        else:
            pending.append(address)

    total = len(unique_addresses)
    log.info("  %d/%d addresses found in local geocode cache", len(results), total)

    def lookup(address: tuple[str, str]):
        blk, street = address
        return address, _geocode_one(f"{blk} {street}", token)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(lookup, address) for address in pending]
        for i, future in enumerate(as_completed(futures), 1):
            address, coords = future.result()
            if coords:
                results[address] = coords
                cache["|".join(address)] = list(coords)
            else:
                log.warning("  No result for: %s %s", *address)
            if i % 100 == 0:
                log.info("  geocoded %d/%d uncached addresses", i, len(pending))

    GEOCODE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOCODE_CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    log.info("Geocoded %d/%d addresses", len(results), total)
    return results


# ── Schools ───────────────────────────────────────────────────────────────────

# data.gov.sg School Directory resource ID
_SCHOOL_RESOURCE_ID = "d_688b934f82c1059ed0a6993d2a829089"


def fetch_schools(
    api_key: str | None = None,
    onemap_token: str | None = None,
) -> list[School]:
    """Fetch school directory from data.gov.sg."""
    log.info("Fetching schools from data.gov.sg…")
    try:
        records = _datagov_fetch_all(_SCHOOL_RESOURCE_ID, limit=500, api_key=api_key)
    except Exception as exc:
        log.warning("School fetch failed (%s); using empty list", exc)
        return []

    coordinates: dict[int, tuple[float, float]] = {}
    if onemap_token:
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(
                    _geocode_one,
                    r.get("postal_code") or r.get("address", ""),
                    onemap_token,
                ): i
                for i, r in enumerate(records, 1)
            }
            for future in as_completed(futures):
                coords = future.result()
                if coords:
                    coordinates[futures[future]] = coords

    schools: list[School] = []
    for i, r in enumerate(records, 1):
        try:
            coords = coordinates.get(i)
            lat = float(r.get("latitude") or r.get("lat_dd") or (coords or (0, 0))[0])
            lon = float(r.get("longitude") or r.get("lon_dd") or (coords or (0, 0))[1])
            if not (1.1 < lat < 1.5 and 103.5 < lon < 104.1):
                continue
            name = r.get("school_name", f"School {i}").strip().upper()
            stype = r.get("mainlevel_code", "PRIMARY").strip().upper()
            schools.append(School(
                school_id=i,
                school_name=name,
                school_type=stype,
                point=Point(lat=lat, lon=lon),
            ))
        except (ValueError, TypeError):
            continue
    log.info("  %d schools loaded", len(schools))
    return schools


# ── MRT Stations ─────────────────────────────────────────────────────────────

def get_mrt_stations() -> list[MrtStation]:
    return [
        MrtStation(
            station_id=sid, station_name=name, line_name=line,
            status=status, opening_year=year,
            point=Point(lat=lat, lon=lon),
        )
        for sid, name, line, status, year, lat, lon in _MRT_STATIONS
    ]


# ── Planning areas from block groupings ───────────────────────────────────────

def _bbox_polygon(blocks: list[Block]) -> list[list[tuple[float, float]]]:
    """Build a rectangular polygon enclosing all blocks (outer ring only)."""
    lons = [b.point.lon for b in blocks]
    lats = [b.point.lat for b in blocks]
    pad = 0.005
    lo0, lo1 = min(lons) - pad, max(lons) + pad
    la0, la1 = min(lats) - pad, max(lats) + pad
    ring = [(lo0, la0), (lo1, la0), (lo1, la1), (lo0, la1), (lo0, la0)]
    return [ring]


def build_planning_areas(blocks: list[Block]) -> list[PlanningArea]:
    """Create a PlanningArea per unique town, bounding its blocks."""
    towns: dict[str, list[Block]] = defaultdict(list)
    for b in blocks:
        towns[b.town].append(b)

    # Assign a stable region based on town name.
    _REGION: dict[str, str] = {
        "TAMPINES": "EAST", "BEDOK": "EAST", "PASIR RIS": "EAST",
        "GEYLANG": "EAST", "MARINE PARADE": "EAST", "CHANGI": "EAST",
        "BISHAN": "CENTRAL", "TOA PAYOH": "CENTRAL", "ANG MO KIO": "CENTRAL",
        "SERANGOON": "CENTRAL", "NOVENA": "CENTRAL", "KALLANG": "CENTRAL",
        "QUEENSTOWN": "CENTRAL", "BUKIT TIMAH": "CENTRAL", "CENTRAL AREA": "CENTRAL",
        "JURONG WEST": "WEST", "JURONG EAST": "WEST", "BUKIT BATOK": "WEST",
        "BUKIT PANJANG": "WEST", "CLEMENTI": "WEST", "CHOA CHU KANG": "WEST",
        "WOODLANDS": "NORTH", "SEMBAWANG": "NORTH", "YISHUN": "NORTH",
        "MANDAI": "NORTH", "SELETAR": "NORTH",
        "PUNGGOL": "NORTH-EAST", "SENGKANG": "NORTH-EAST",
        "HOUGANG": "NORTH-EAST", "BUANGKOK": "NORTH-EAST",
    }

    areas: list[PlanningArea] = []
    for area_id, (town, blks) in enumerate(sorted(towns.items()), start=1):
        region = _REGION.get(town.upper(), "CENTRAL")
        polygon = _bbox_polygon(blks)
        areas.append(PlanningArea(
            planning_area_id=area_id,
            name=town.upper(),
            region=region,
            polygon=polygon,
        ))
    return areas


# ── Main assembler ────────────────────────────────────────────────────────────

def fetch_dataset(onemap_token: str, months: int = 120,
                  datagov_api_key: str | None = None) -> Dataset:
    """Fetch all live data and return a Dataset."""

    # 1. Raw HDB transactions
    raw_txns = fetch_hdb_transactions(months=months, api_key=datagov_api_key)
    if not raw_txns:
        raise RuntimeError("No HDB transaction data returned from data.gov.sg")

    # 2. Unique (block, street) pairs to geocode
    unique_addr: list[tuple[str, str]] = list({
        (r["block"], r["street_name"]) for r in raw_txns
    })
    log.info("Geocoding %d unique block addresses via OneMap…", len(unique_addr))
    coords_map = geocode_blocks(unique_addr, onemap_token)

    # 3. Build Block objects (one per unique address that geocoded successfully)
    blocks: list[Block] = []
    addr_to_block_id: dict[tuple[str, str], int] = {}
    for blk_id, (blk_no, street) in enumerate(
        sorted(coords_map.keys()), start=1
    ):
        lat, lon = coords_map[(blk_no, street)]
        # Find a representative transaction for town + lease year
        sample = next(
            (r for r in raw_txns if r["block"] == blk_no and r["street_name"] == street),
            None,
        )
        if sample is None:
            continue
        town = sample.get("town", "UNKNOWN").strip().upper()
        lease_year = int(str(sample.get("lease_commence_date", "1980"))[:4])
        blocks.append(Block(
            block_id=blk_id,
            block_number=blk_no,
            street_name=street,
            postal_code="",
            town=town,
            planning_area_id=None,  # resolved by ingest()
            lease_commencement_year=lease_year,
            point=Point(lat=lat, lon=lon),
        ))
        addr_to_block_id[(blk_no, street)] = blk_id

    log.info("Built %d block objects", len(blocks))

    # 4. Build Transaction objects
    transactions: list[Transaction] = []
    txn_id = 1
    for r in raw_txns:
        key = (r["block"], r["street_name"])
        blk_id = addr_to_block_id.get(key)
        if blk_id is None:
            continue
        try:
            transactions.append(Transaction(
                transaction_id=txn_id,
                block_id=blk_id,
                transaction_month=r["month"] + "-01",
                resale_price=float(r["resale_price"]),
                floor_area_sqm=float(r["floor_area_sqm"]),
                flat_type=r["flat_type"].strip().upper(),
                storey_range=r.get("storey_range", "01 TO 03"),
            ))
            txn_id += 1
        except (KeyError, ValueError):
            continue

    log.info("Built %d transactions", len(transactions))

    # 5. Reference layers
    mrt_stations = get_mrt_stations()
    schools = fetch_schools(
        api_key=datagov_api_key,
        onemap_token=onemap_token,
    )

    # 6. Planning areas from block town groups
    planning_areas = build_planning_areas(blocks)

    return Dataset(
        planning_areas=planning_areas,
        mrt_stations=mrt_stations,
        bus_stops=[],      # LTA DataMall requires separate registration
        schools=schools,
        bto_projects=[],
        blocks=blocks,
        transactions=transactions,
    )
