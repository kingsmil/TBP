"""Precompute per-block amenity counts within ~1 km, for the client's Lifestyle
score. Counts are stored per amenity (incl. schools from block_proximity); the
browser applies the user's weights at read time. Refreshed with the amenity seed.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

log = logging.getLogger(__name__)

# Radius for "within walking distance". MUST match the frontend
# LIFESTYLE_RADIUS_KM (lib/lifestyle.ts). Changing it requires a rebuild.
RADIUS_M = 1000

_BUILD_SQL = text(
    """
    INSERT INTO block_amenity_counts (block_id, counts, updated_at)
    SELECT b.block_id,
           jsonb_build_object('schools', COALESCE(p.schools_within_1km, 0))
             || COALESCE(ac.counts, '{}'::jsonb),
           now()
    FROM hdb_blocks b
    LEFT JOIN block_proximity p ON p.block_id = b.block_id
    LEFT JOIN LATERAL (
        SELECT jsonb_object_agg(t.amenity, t.cnt) AS counts
        FROM (
            SELECT ap.amenity, count(*) AS cnt
            FROM amenity_pois ap
            WHERE ST_DWithin(ap.geom_svy21, b.geom_svy21, :radius)
            GROUP BY ap.amenity
        ) t
    ) ac ON true
    ON CONFLICT (block_id) DO UPDATE
       SET counts = EXCLUDED.counts, updated_at = now();
    """
)


def rebuild(engine, radius_m: int = RADIUS_M) -> int:
    """Recompute counts for every block. Returns the number of rows written."""
    with engine.begin() as conn:
        conn.execute(_BUILD_SQL, {"radius": radius_m})
        n = conn.execute(text("SELECT count(*) FROM block_amenity_counts")).scalar() or 0
    log.info("Rebuilt block_amenity_counts for %d blocks (radius=%dm).", n, radius_m)
    return int(n)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    from app.api.deps import get_engine_or_none
    engine = get_engine_or_none()
    if engine is None:
        log.error("No database configured (set DATABASE_URL).")
        return 0
    return rebuild(engine)


if __name__ == "__main__":
    main()
