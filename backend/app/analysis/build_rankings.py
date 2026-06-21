"""Build + store appreciation rankings.

    python -m app.analysis.build_rankings              # 10-year window
    python -m app.analysis.build_rankings --years 5

Run after seeding and monthly via cron. Reads the live PostGIS data, computes
region + block appreciation rankings, and replaces the ranking tables.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from app.analysis import appreciation_rankings as ar

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build appreciation rankings")
    parser.add_argument("--years", type=int, default=ar.DEFAULT_WINDOW_YEARS,
                        help="Analysis window in years (default 10)")
    args = parser.parse_args()

    from app.api.deps import get_engine_or_none, get_repository
    engine = get_engine_or_none()
    if engine is None:
        log.error("No PostGIS database (DATABASE_URL unset/unreachable) — "
                  "rankings need live data to compute and store.")
        return 2

    repo = get_repository()
    log.info("Computing %d-year appreciation rankings…", args.years)
    t0 = time.time()
    blocks, regions = ar.build_rankings(repo, years=args.years)
    log.info("Ranked %d blocks and %d regions in %.1fs.",
             len(blocks), len(regions), time.time() - t0)

    if not blocks and not regions:
        log.warning("Nothing to store — is the data seeded? (no qualifying rows)")
        return 1

    ar.persist(engine, blocks, regions)
    log.info("Stored rankings (computed_at = now).")

    if regions:
        top = regions[0]
        log.info("Top region: %s — %.1f%% CAGR (%d→%d)",
                 top.name, top.cagr_pct, top.year_start, top.year_end)
    return 0


if __name__ == "__main__":
    sys.exit(main())
