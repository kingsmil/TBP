"""Load live HDB resale transactions from data.gov.sg into PostGIS.

The data.gov.sg resale dataset has transaction attributes but no geometry. This
loader derives unique HDB blocks from transaction rows and resolves each block
with OneMap search so the existing spatial schema can still be used.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Iterable

import httpx
from sqlalchemy import text

from app.core.geo import Point
from app.core.models import Block, Transaction
from app.db.maintenance import refresh_materialized_views
from app.db.session import get_engine
from app.repositories.postgis import PostgisRepository

DATASET_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"
ONEMAP_SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"


@dataclass(frozen=True)
class LoadReport:
    records_seen: int
    blocks_loaded: int
    transactions_loaded: int
    geocode_misses: int


def make_block_id(block: str, street_name: str) -> int:
    key = f"{block.strip().upper()}|{street_name.strip().upper()}"
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=6).hexdigest()
    return int(digest, 16)


def transaction_from_record(record: dict) -> Transaction:
    month = str(record["month"])
    return Transaction(
        transaction_id=int(record["_id"]),
        block_id=make_block_id(str(record["block"]), str(record["street_name"])),
        transaction_month=f"{month}-01",
        resale_price=float(record["resale_price"]),
        floor_area_sqm=float(record["floor_area_sqm"]),
        flat_type=str(record["flat_type"]).upper(),
        storey_range=str(record.get("storey_range") or ""),
    )


def block_from_record(record: dict, geocode: dict) -> Block:
    return Block(
        block_id=make_block_id(str(record["block"]), str(record["street_name"])),
        block_number=str(record["block"]).strip().upper(),
        street_name=str(record["street_name"]).strip().upper(),
        postal_code=str(geocode.get("POSTAL") or ""),
        town=str(record["town"]).strip().upper(),
        planning_area_id=None,
        lease_commencement_year=int(record["lease_commence_date"]),
        point=Point(float(geocode["LONGITUDE"]), float(geocode["LATITUDE"])),
    )


def fetch_resale_records(client: httpx.Client, limit: int | None, page_size: int) -> list[dict]:
    records: list[dict] = []
    offset = 0
    while True:
        batch_limit = page_size if limit is None else min(page_size, limit - len(records))
        if batch_limit <= 0:
            break
        response = client.get(
            DATASTORE_URL,
            params={"resource_id": DATASET_ID, "limit": batch_limit, "offset": offset},
        )
        response.raise_for_status()
        payload = response.json()
        result = payload["result"]
        batch = result["records"]
        records.extend(batch)
        offset += len(batch)
        if len(batch) < batch_limit or len(records) >= int(result["total"]):
            break
    return records


def geocode_block(client: httpx.Client, record: dict, retries: int = 3) -> dict | None:
    query = f"{record['block']} {record['street_name']}"
    headers = {}
    token = os.environ.get("ONEMAP_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(retries):
        response = client.get(
            ONEMAP_SEARCH_URL,
            params={"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1},
            headers=headers,
        )
        if response.status_code == 429 and attempt < retries - 1:
            time.sleep(2 ** attempt)
            continue
        if response.status_code >= 400:
            return None
        results = response.json().get("results") or []
        best = _best_geocode(results, record["block"], record["street_name"])
        if best is not None:
            return best
    return None


# HDB street abbreviations -> OneMap's full ROAD_NAME, so we can verify the match
# instead of blindly trusting OneMap's fuzzy top result (which once matched
# "JALAN JAMBU BATU" for "JLN BATU").
_ROAD_ABBREV = {
    "JLN": "JALAN", "RD": "ROAD", "AVE": "AVENUE", "ST": "STREET", "DR": "DRIVE",
    "CRES": "CRESCENT", "CL": "CLOSE", "BT": "BUKIT", "UPP": "UPPER", "LOR": "LORONG",
    "TG": "TANJONG", "GDNS": "GARDENS", "PK": "PARK", "TER": "TERRACE", "NTH": "NORTH",
    "STH": "SOUTH", "CTRL": "CENTRAL", "MKT": "MARKET", "KG": "KAMPONG", "HTS": "HEIGHTS",
    "PL": "PLACE", "SQ": "SQUARE", "CTR": "CENTRE", "C'WEALTH": "COMMONWEALTH",
}


def _norm_road(name: str) -> str:
    return " ".join(_ROAD_ABBREV.get(t, t) for t in (name or "").upper().split())


def _best_geocode(results: list[dict], block: str, street: str) -> dict | None:
    """Prefer a result that actually matches the block + road; fall back to the
    first geocoded result only if nothing matches."""
    want = _norm_road(street)
    has_xy = [r for r in results if r.get("LATITUDE") and r.get("LONGITUDE")]
    for r in has_xy:  # exact: same block number AND road
        if str(r.get("BLK_NO")) == str(block) and r.get("ROAD_NAME", "").upper() == want:
            return r
    for r in has_xy:  # road matches (any block)
        if r.get("ROAD_NAME", "").upper() == want:
            return r
    return has_xy[0] if has_xy else None


def unique_block_records(records: Iterable[dict]) -> list[dict]:
    seen: set[int] = set()
    unique = []
    for record in records:
        block_id = make_block_id(str(record["block"]), str(record["street_name"]))
        if block_id in seen:
            continue
        seen.add(block_id)
        unique.append(record)
    return unique


def replace_postgis_data(repo: PostgisRepository, blocks: list[Block], txns: list[Transaction]) -> None:
    engine = repo._engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE block_proximity, hdb_transactions, hdb_blocks RESTART IDENTITY CASCADE"))
    repo.add_blocks(blocks)
    repo.add_transactions(txns)
    refresh_materialized_views(engine)


def load(limit: int | None = None, page_size: int = 1000, geocode_pause_s: float = 0.05) -> LoadReport:
    engine = get_engine()
    repo = PostgisRepository(engine)
    timeout = httpx.Timeout(30.0)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        records = fetch_resale_records(client, limit=limit, page_size=page_size)
        blocks: list[Block] = []
        geocode_misses = 0
        for record in unique_block_records(records):
            geocode = geocode_block(client, record)
            if geocode is None:
                geocode_misses += 1
                continue
            blocks.append(block_from_record(record, geocode))
            if geocode_pause_s:
                time.sleep(geocode_pause_s)

    block_ids = {block.block_id for block in blocks}
    txns = [transaction_from_record(record) for record in records
            if make_block_id(str(record["block"]), str(record["street_name"])) in block_ids]
    replace_postgis_data(repo, blocks, txns)
    return LoadReport(len(records), len(blocks), len(txns), geocode_misses)


def main() -> int:
    limit_env = os.environ.get("DATA_GOV_LIMIT", "5000").strip()
    limit = None if limit_env.lower() in {"", "all", "none"} else int(limit_env)
    page_size = int(os.environ.get("DATA_GOV_PAGE_SIZE", "1000"))
    pause = float(os.environ.get("ONEMAP_GEOCODE_PAUSE_S", "0.05"))
    report = load(limit=limit, page_size=page_size, geocode_pause_s=pause)
    print("data.gov.sg load complete:")
    print(f"  records seen        : {report.records_seen}")
    print(f"  blocks loaded       : {report.blocks_loaded}")
    print(f"  transactions loaded : {report.transactions_loaded}")
    print(f"  geocode misses      : {report.geocode_misses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
