"""URA private-transaction ingestion: one-time seed + monthly cron refresh.

Pulls the rolling ~60-month dataset from URA once and stores it in
private_transactions, so client requests + server restarts read from PostGIS
instead of re-hitting URA. Refreshed monthly by the background scheduler.

CLI (seed / manual refresh):  python -m app.data.ura
"""
from __future__ import annotations

import logging

from app.services.private_property import ura_client, store

log = logging.getLogger(__name__)


def rebuild(engine) -> int:
    """Fetch the latest transactions (live URA, or fixtures in mock mode) and
    persist them. Returns the row count stored."""
    rows = ura_client.refresh()
    if not rows:
        log.warning("URA returned no rows — keeping existing stored data.")
        return 0
    n = store.persist(engine, rows)
    log.info("Stored %d private (URA) transactions.", n)
    return n


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from app.api.deps import get_engine_or_none
    engine = get_engine_or_none()
    if engine is None:
        log.error("No PostGIS database (DATABASE_URL unset/unreachable).")
        return 2
    if ura_client.is_mock():
        log.warning("URA_ACCESS_KEY not set — seeding from bundled fixtures.")
    n = rebuild(engine)
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
