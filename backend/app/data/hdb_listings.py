"""HDB Flat Portal active-listings ingestion.

Fetches live resale listings from the official HDB Flat Portal public API and
matches each to one of our blocks (one Block -> 0..N ActiveListings):

  1. POST map/getCoordinatesByFilters   -> all resale listing ids
  2. POST listing/resale/detailsJdbc    -> flat detail per id
  3. tiered match to a block: postal exact, then normalized block+street
  4. repo.add_active_listings(matched)  -> idempotent upsert by listing_id

Agent contact fields (name/phone/email/agency) are usually null in the public
detail payload — the portal gates seller contact behind login. We store them
when present and leave them None otherwise.

CLI: python -m app.data.hdb_listings [--limit N]
"""
from __future__ import annotations

import argparse
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from app.core.models import ActiveListing, Block
from app.repositories.base import Repository

log = logging.getLogger(__name__)

_BASE = "https://api.homes.hdb.gov.sg/flatback/public/v1"
_PORTAL = "https://homes.hdb.gov.sg"

# All-Singapore resale filter — mirrors the portal map's default query.
_MARKER_FILTERS = {
    "town": "", "location": "", "range": "2", "classification": "",
    "priceRangeLower": "0", "priceRangeUpper": "0", "flatType": "",
    "waitingTime": "", "modeOfSale": "", "remainingLeaseRangeLower": 1,
    "remainingLeaseRangeUpper": 99, "salesPerson": False, "floorRange": "",
    "ethnicGroup": "", "citizenship": "", "extension": "", "contra": "",
    "rank": "Location, Price Range, Flat Type, Remaining Lease",
    "coordinates": [["", ""]], "fullResult": False,
}


# ---------------------------------------------------------------------------
# Listing -> block matching
# ---------------------------------------------------------------------------

_ROAD_ABBREV = {
    "ROAD": "RD", "AVENUE": "AVE", "STREET": "ST", "DRIVE": "DR",
    "CRESCENT": "CRES", "CLOSE": "CL", "PLACE": "PL", "TERRACE": "TER",
    "GARDENS": "GDNS", "HEIGHTS": "HTS", "NORTH": "NTH", "SOUTH": "STH",
    "CENTRAL": "CTRL", "UPPER": "UPP", "COMMONWEALTH": "C'WEALTH",
    "PARK": "PK", "LANE": "LN",
}


def normalize_street(s: str) -> str:
    """Uppercase, collapse whitespace, and apply HDB road abbreviations."""
    words = re.sub(r"[^\w\s.']", " ", (s or "").upper()).split()
    return " ".join(_ROAD_ABBREV.get(w, w) for w in words)


class BlockMatcher:
    """Tiered listing->block resolution: postal exact, then norm(block)+norm(street)."""

    def __init__(self, blocks: Sequence[Block]):
        self._by_postal = {b.postal_code: b.block_id for b in blocks if b.postal_code}
        self._by_addr = {
            (b.block_number.strip().upper(), normalize_street(b.street_name)): b.block_id
            for b in blocks
        }

    def match(self, postal: str, block: str, street: str) -> tuple[int | None, int]:
        """Return (block_id, tier) — tier 1 postal, 2 block+street, 0 no match."""
        bid = self._by_postal.get((postal or "").strip())
        if bid is not None:
            return bid, 1
        key = ((block or "").strip().upper(), normalize_street(street or ""))
        bid = self._by_addr.get(key)
        if bid is not None:
            return bid, 2
        return None, 0


# ---------------------------------------------------------------------------
# Detail parsing
# ---------------------------------------------------------------------------

def parse_detail(raw: dict[str, Any], listing_id: int) -> dict[str, Any]:
    """Map a detailsJdbc payload to ActiveListing kwargs (minus block_id)."""
    desc_entries = raw.get("description") or [{}]
    first = desc_entries[0] if desc_entries else {}
    return {
        "listing_id": int(listing_id),
        "block_number": str(raw.get("block") or "").strip().upper(),
        "street_name": str(raw.get("street") or "").strip().upper(),
        "postal_code": str(raw.get("postal") or "").strip(),
        "town": str(raw.get("town") or "").strip(),
        "price": float(raw.get("price") or 0),
        "flat_type": str(raw.get("flatType") or ""),
        "floor_area_sqm": float(raw.get("floorArea") or 0),
        "storey_range": str(raw.get("storeyRange") or ""),
        "remaining_lease": str(raw.get("remainingLease") or ""),
        "bedroom": raw.get("bedroom"),
        "bathroom": raw.get("bathroom"),
        "description": first.get("description"),
        "photo_path": raw.get("photo"),
        "agent_name": first.get("name"),
        "agent_phone": first.get("number"),
        "agent_email": first.get("email"),
        "agency_name": first.get("agencyName"),
        "managed_by_agent": bool(raw.get("managedByAgent")),
        "last_updated": str(first.get("lastUpdated") or ""),
    }


# ---------------------------------------------------------------------------
# HTTP client (httpx; browser-like headers for CloudFront)
# ---------------------------------------------------------------------------

def _make_client():
    import os

    import httpx

    xsrf = os.environ.get("HDB_XSRF_TOKEN", "")
    cookie = os.environ.get("HDB_HOMES_COOKIE", "")
    headers = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) "
                       "Gecko/20100101 Firefox/148.0"),
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": f"{_PORTAL}/",
        "Origin": _PORTAL,
    }
    client = httpx.Client(headers=headers, timeout=30.0, follow_redirects=True)
    if xsrf and cookie:
        client.cookies.set("XSRF-TOKEN", xsrf, domain="api.homes.hdb.gov.sg")
        client.cookies.set("HDB_HOMES", cookie, domain="api.homes.hdb.gov.sg")
    else:
        # Bootstrap a session: a GET to the public user-details endpoint mints
        # fresh XSRF-TOKEN + HDB_HOMES cookies on the api.homes domain.
        try:
            client.get(f"{_BASE}/user/user-details")
            xsrf = client.cookies.get("XSRF-TOKEN") or xsrf
        except Exception as exc:  # pragma: no cover - network only
            log.warning("portal session bootstrap failed: %s", exc)
    if xsrf:
        client.headers["X-XSRF-TOKEN"] = xsrf
    return client


def fetch_markers(client=None) -> list[str]:
    """All current resale listing ids from the portal map endpoint."""
    client = client or _make_client()
    resp = client.post(f"{_BASE}/map/getCoordinatesByFilters", json=_MARKER_FILTERS)
    resp.raise_for_status()
    ids: list[str] = []
    for marker in resp.json():
        props = marker.get("props") or {}
        if props.get("type") != "Resale":
            continue
        for d in props.get("desc") or []:
            if d.get("id"):
                ids.append(str(d["id"]))
    return ids


def fetch_detail(listing_id: str, client=None) -> dict[str, Any]:
    client = client or _make_client()
    resp = client.post(f"{_BASE}/listing/resale/detailsJdbc",
                       json={"listingId": str(listing_id)})
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

@dataclass
class ListingIngestReport:
    listings_fetched: int = 0
    matched_tier1: int = 0
    matched_tier2: int = 0
    unmatched: int = 0
    fetch_errors: int = 0

    @property
    def matched(self) -> int:
        return self.matched_tier1 + self.matched_tier2


def ingest_listings(
    repo: Repository,
    fetch_markers: Callable[[], list[str]],
    fetch_detail: Callable[[str], dict[str, Any]],
    limit: int | None = None,
    delay_s: float = 0.0,
) -> ListingIngestReport:
    """Fetch markers -> details, match to blocks, upsert into the repository."""
    report = ListingIngestReport()
    matcher = BlockMatcher(repo.blocks())
    ids = fetch_markers()
    if limit is not None:
        ids = ids[:limit]
    matched: list[ActiveListing] = []
    for lid in ids:
        try:
            raw = fetch_detail(lid)
        except Exception as exc:
            report.fetch_errors += 1
            log.warning("detail fetch failed for %s: %s", lid, exc)
            continue
        report.listings_fetched += 1
        fields = parse_detail(raw, int(lid))
        block_id, tier = matcher.match(
            fields["postal_code"], fields["block_number"], fields["street_name"])
        if block_id is None:
            report.unmatched += 1
            continue
        if tier == 1:
            report.matched_tier1 += 1
        else:
            report.matched_tier2 += 1
        matched.append(ActiveListing(block_id=block_id, **fields))
        if delay_s:
            time.sleep(delay_s)
    if matched:
        repo.add_active_listings(matched)
    return report


def main() -> None:  # pragma: no cover - CLI/network entry point
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Load HDB Flat Portal listings")
    parser.add_argument("--limit", type=int, default=None,
                        help="max listings to fetch (default: all)")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="seconds between detail calls (politeness)")
    args = parser.parse_args()

    from app.api.deps import get_repository
    repo = get_repository()
    client = _make_client()
    report = ingest_listings(
        repo,
        fetch_markers=lambda: fetch_markers(client),
        fetch_detail=lambda lid: fetch_detail(lid, client),
        limit=args.limit,
        delay_s=args.delay,
    )
    log.info(
        "listings: fetched=%d matched_tier1=%d matched_tier2=%d unmatched=%d errors=%d",
        report.listings_fetched, report.matched_tier1, report.matched_tier2,
        report.unmatched, report.fetch_errors,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
