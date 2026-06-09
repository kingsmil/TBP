"""Maintenance jobs: rebuild proximity + refresh analytics MVs.

In production these become Celery tasks triggered after ingestion. Here they
are plain functions / a CLI. Run:  python -m app.db.maintenance
"""
from __future__ import annotations

import pathlib
import sys

from sqlalchemy import text

from app.db.session import get_engine

PROX_SQL = (pathlib.Path(__file__).parent / "maintenance.sql").read_text()
MVS = ("mv_block_monthly_stats", "mv_estate_monthly_stats")


def rebuild_proximity(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(PROX_SQL))


def refresh_materialized_views(engine) -> None:
    # CONCURRENTLY needs the MV to be populated once first; fall back on error.
    for mv in MVS:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}"))
        except Exception:
            with engine.begin() as conn:
                conn.execute(text(f"REFRESH MATERIALIZED VIEW {mv}"))


def main() -> int:
    engine = get_engine()
    print("rebuilding proximity ...")
    rebuild_proximity(engine)
    print("refreshing materialized views ...")
    refresh_materialized_views(engine)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
