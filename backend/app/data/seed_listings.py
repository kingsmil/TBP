"""Seed active listings from the bundled HDB Flat Portal snapshot.

The snapshot (app/data/snapshots/active_listings.csv) is a recorded export
of the portal's live resale listings, so demos work without the ~25-minute
throttled live ingest (use `python -m app.data.hdb_listings` to refresh).
Rows are re-matched to blocks at load time — block ids are not stable
across reseeds — so this works against any seeded database.

Usage:
    python -m app.data.seed_listings              # load bundled snapshot
    python -m app.data.seed_listings --csv other.csv
"""
from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from typing import Any

from app.core.models import ActiveListing
from app.data.hdb_listings import BlockMatcher
from app.repositories.base import Repository

log = logging.getLogger(__name__)

SNAPSHOT = Path(__file__).parent / "snapshots" / "active_listings.csv"


def _opt_int(v: str | None) -> int | None:
    return int(v) if v not in (None, "") else None


def _opt_str(v: str | None) -> str | None:
    return v or None


def row_to_fields(row: dict[str, str]) -> dict[str, Any]:
    """Map a snapshot CSV row to ActiveListing kwargs (minus block_id)."""
    return {
        "listing_id": int(row["listing_id"]),
        "block_number": row["block_number"],
        "street_name": row["street_name"],
        "postal_code": row["postal_code"],
        "town": row["town"],
        "price": float(row["price"]),
        "flat_type": row["flat_type"],
        "floor_area_sqm": float(row["floor_area_sqm"]),
        "storey_range": row["storey_range"],
        "remaining_lease": row["remaining_lease"],
        "bedroom": _opt_int(row["bedroom"]),
        "bathroom": _opt_int(row["bathroom"]),
        "description": _opt_str(row["description"]),
        "photo_path": _opt_str(row["photo_path"]),
        "agent_name": _opt_str(row["agent_name"]),
        "agent_phone": _opt_str(row["agent_phone"]),
        "agent_email": _opt_str(row["agent_email"]),
        "agency_name": _opt_str(row["agency_name"]),
        "managed_by_agent": row["managed_by_agent"].strip().lower() in ("t", "true", "1"),
        "last_updated": row["last_updated"],
    }


def seed_listings(repo: Repository, csv_path: Path = SNAPSHOT) -> tuple[int, int]:
    """Load snapshot rows and match each to a current block.

    Returns (seeded, unmatched). Unmatched rows (block absent from this
    database's hdb_blocks) are skipped, mirroring the live ingester.
    """
    matcher = BlockMatcher(repo.blocks())
    loaded: list[ActiveListing] = []
    unmatched = 0
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            fields = row_to_fields(row)
            block_id, _tier = matcher.match(
                fields["postal_code"], fields["block_number"], fields["street_name"])
            if block_id is None:
                unmatched += 1
                continue
            loaded.append(ActiveListing(block_id=block_id, **fields))
    if loaded:
        repo.add_active_listings(loaded)
    return len(loaded), unmatched


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Seed active listings from a CSV snapshot")
    parser.add_argument("--csv", type=Path, default=SNAPSHOT,
                        help="snapshot path (default: bundled)")
    args = parser.parse_args()
    if not args.csv.exists():
        log.error("snapshot not found: %s", args.csv)
        return 2

    from app.api.deps import get_repository
    repo = get_repository()
    seeded, unmatched = seed_listings(repo, args.csv)
    log.info("active listings: seeded=%d unmatched=%d", seeded, unmatched)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
