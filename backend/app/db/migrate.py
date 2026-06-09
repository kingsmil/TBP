"""Apply ordered SQL migrations to PostGIS.

Deliberately simple: plain ordered .sql files tracked in a `schema_migrations`
table. We avoid ORM autogeneration because it does not handle PostGIS geometry,
declarative partitioning, or materialized views well.

Run with a live PostGIS DB:  python -m app.db.migrate
Requires: psycopg, DATABASE_URL env var.
"""
from __future__ import annotations

import os
import pathlib
import sys

SQL_DIR = pathlib.Path(__file__).parent / "migrations" / "sql"


def discover() -> list[pathlib.Path]:
    """Return migration files sorted by their numeric prefix."""
    return sorted(SQL_DIR.glob("*.sql"), key=lambda p: p.name)


def applied_versions(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT to_regclass('schema_migrations')"
        )
        if cur.fetchone()[0] is None:
            return set()
        cur.execute("SELECT version FROM schema_migrations")
        return {r[0] for r in cur.fetchall()}


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2
    try:
        import psycopg
    except ImportError:
        print("psycopg not installed; run `pip install -r requirements.txt`",
              file=sys.stderr)
        return 2

    files = discover()
    with psycopg.connect(dsn) as conn:
        done = applied_versions(conn)
        for path in files:
            version = path.stem
            if version in done:
                print(f"skip   {version}")
                continue
            print(f"apply  {version}")
            with conn.cursor() as cur:
                cur.execute(path.read_text())
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s) "
                    "ON CONFLICT DO NOTHING",
                    (version,),
                )
            conn.commit()
    print("migrations complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
