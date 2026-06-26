"""Amenity-POI ingestion: one-time seed + monthly cron refresh.

Pulls the OneMap-sourced amenity layers (parks, hawker centres, hospitals, …)
once into amenity_pois so the map doesn't re-hit the OneMap Themes API on every
server restart. Schools are not stored here — they come from our reference layer.

CLI:  python -m app.data.amenities
"""
from __future__ import annotations

import logging

from app.services import amenities as svc

log = logging.getLogger(__name__)


def rebuild(engine) -> int:
    """Fetch every OneMap-sourced amenity layer and persist it. Returns total POIs."""
    total = 0
    for key in svc.onemap_keys():
        try:
            rows = svc.fetch_for_seed(key)
            n = svc.persist(engine, key, rows)
            total += n
            log.info("Stored %d %s POIs.", n, key)
        except Exception as exc:
            log.warning("Amenity '%s' seed failed: %s", key, exc)
    return total


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from app.api.deps import get_engine_or_none
    engine = get_engine_or_none()
    if engine is None:
        log.error("No PostGIS database (DATABASE_URL unset/unreachable).")
        return 2
    total = rebuild(engine)
    log.info("Stored %d amenity POIs across %d layers.", total, len(svc.onemap_keys()))
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
