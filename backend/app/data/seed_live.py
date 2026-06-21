"""Seed PostGIS with live HDB data from data.gov.sg + OneMap.

Usage:
    python -m app.data.seed_live              # last 120 months (10 years)
    python -m app.data.seed_live --months 24  # last 24 months

Requires:
    DATABASE_URL  — PostGIS connection string (set in .env)
    ONEMAP_TOKEN  — OneMap API token (set in .env)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed PostGIS with live HDB data")
    parser.add_argument("--months", type=int, default=120,
                        help="How many months of HDB transactions to fetch "
                             "(default 120 = 10 years, for appreciation analysis)")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    from app.services.commute import onemap_auth
    onemap_token = onemap_auth.current_token()  # static token or minted from creds
    datagov_api_key = os.environ.get("DATAGOV_API_KEY") or None

    if not database_url:
        log.error("DATABASE_URL not set — cannot seed PostGIS.")
        return 2
    if not onemap_token:
        log.error("OneMap not configured — required for geocoding block addresses.")
        log.error("Set ONEMAP_EMAIL/ONEMAP_PASSWORD (or ONEMAP_TOKEN) in .env.")
        log.error("Register free at https://www.onemap.gov.sg/apidocs/register")
        return 2

    log.info("Fetching live dataset (%d months)…", args.months)
    try:
        from sqlalchemy import text
        from app.db.session import get_engine

        with get_engine().connect() as conn:
            block_count = conn.execute(text(
                "SELECT COUNT(*) FROM hdb_blocks"
            )).scalar() or 0
        if block_count >= 100:
            log.info("Live data is already loaded (%d blocks); skipping external API preload.", block_count)
            return 0
        if block_count > 0:
            log.warning("Only %d block(s) found — looks like stale/test data; re-seeding.", block_count)
    except Exception as exc:
        log.warning("Could not check existing preload state (%s); continuing.", exc)

    if datagov_api_key:
        log.info("Using DATAGOV_API_KEY via the x-api-key request header.")
    else:
        log.warning("DATAGOV_API_KEY is not set; lower Data.gov.sg rate limits apply.")

    try:
        from app.data.fetch_live import fetch_dataset
        dataset = fetch_dataset(onemap_token=onemap_token, months=args.months,
                                datagov_api_key=datagov_api_key)
    except Exception as exc:
        log.error("Failed to fetch live data: %s", exc)
        return 1

    log.info("Ingesting into PostGIS…")
    try:
        from app.db.session import get_engine
        from app.repositories.postgis import PostgisRepository
        from app.data.ingest import ingest

        engine = get_engine()
        repo = PostgisRepository(engine)
        report = ingest(dataset, repo)
    except Exception as exc:
        log.error("Ingestion failed: %s", exc)
        return 1

    log.info("Live seed complete:")
    log.info("  planning areas : %d", len(dataset.planning_areas))
    log.info("  mrt stations   : %d", len(dataset.mrt_stations))
    log.info("  schools        : %d", len(dataset.schools))
    log.info("  blocks loaded  : %d", report.blocks_loaded)
    log.info("  with area FK   : %d", report.blocks_with_planning_area)
    log.info("  transactions   : %d", report.transactions_loaded)
    log.info("  proximity rows : %d", report.proximity_rows)
    log.info("  rejected blocks: %d", report.blocks_rejected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
