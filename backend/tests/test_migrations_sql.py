"""Cross-check the PostGIS SQL migrations against the schema manifest.

These tests do not need a database. They parse the migration .sql files and
assert the geospatial-first invariants that PostGIS will later enforce, so a
broken migration is caught here rather than at `make db-migrate` time.
"""
import pathlib
import re
import unittest

from app.schema import SPATIAL_TABLES
from app.schema.manifest import SRID_SVY21, SRID_WGS84

SQL_DIR = pathlib.Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "sql"


def load_sql() -> str:
    files = sorted(SQL_DIR.glob("*.sql"))
    assert files, f"no migration files found in {SQL_DIR}"
    return "\n".join(p.read_text() for p in files)


def create_block(sql: str, table: str) -> str:
    """Return the CREATE TABLE <table> ( ... ; statement text."""
    m = re.search(r"CREATE TABLE " + re.escape(table) + r"\s*\(", sql)
    assert m, f"CREATE TABLE {table} not found"
    end = sql.index(";", m.start())
    return sql[m.start():end]


class TestMigrationsSql(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = load_sql()

    def test_postgis_extension_enabled(self):
        self.assertRegex(self.sql, r"CREATE EXTENSION IF NOT EXISTS postgis")

    def test_homeos_cases_table_created(self):
        self.assertRegex(
            self.sql,
            r"CREATE TABLE IF NOT EXISTS homeos_cases\s*\(",
            "missing CREATE TABLE homeos_cases",
        )
        # Must be user-scoped and JSONB-backed.
        block = self.sql[self.sql.index("homeos_cases"):]
        self.assertRegex(block, r"user_id\s+INTEGER", "homeos_cases needs user_id INTEGER")
        self.assertRegex(block, r"data\s+JSONB", "homeos_cases needs data JSONB")

    def test_every_spatial_table_created(self):
        for t in SPATIAL_TABLES:
            self.assertRegex(self.sql, r"CREATE TABLE " + re.escape(t.name) + r"\s*\(",
                             f"missing CREATE TABLE {t.name}")

    def test_spatial_tables_dual_geometry(self):
        for t in SPATIAL_TABLES:
            block = create_block(self.sql, t.name)
            self.assertRegex(
                block, rf"geom\s+geometry\([A-Za-z]+,\s*{SRID_WGS84}\)",
                f"{t.name}.geom must be geometry(...,{SRID_WGS84})")
            self.assertRegex(
                block,
                rf"geom_svy21\s+geometry\([A-Za-z]+,\s*{SRID_SVY21}\)",
                f"{t.name}.geom_svy21 must be geometry(...,{SRID_SVY21})")
            self.assertRegex(
                block, r"geom_svy21[\s\S]*GENERATED ALWAYS AS \(ST_Transform\(geom,\s*3414\)\) STORED",
                f"{t.name}.geom_svy21 must be a generated ST_Transform column")

    def test_spatial_tables_have_gist_indexes(self):
        for t in SPATIAL_TABLES:
            self.assertRegex(
                self.sql, rf"CREATE INDEX \w+\s+ON {re.escape(t.name)} USING gist \(geom\)",
                f"{t.name} missing GIST index on geom")
            self.assertRegex(
                self.sql, rf"CREATE INDEX \w+\s+ON {re.escape(t.name)} USING gist \(geom_svy21\)",
                f"{t.name} missing GIST index on geom_svy21")

    def test_transactions_partitioned(self):
        self.assertRegex(self.sql, r"PARTITION BY RANGE \(transaction_month\)")
        self.assertGreaterEqual(
            len(re.findall(r"PARTITION OF hdb_transactions", self.sql)), 5,
            "expected several yearly partitions")

    def test_transactions_generated_columns(self):
        block = create_block(self.sql, "hdb_transactions")
        self.assertRegex(block, r"psf\s+numeric[\s\S]*GENERATED ALWAYS AS")
        self.assertRegex(block, r"floor_area_sqft\s+numeric[\s\S]*GENERATED ALWAYS AS")

    def test_materialized_views_have_unique_index(self):
        for mv in ("mv_block_monthly_stats", "mv_estate_monthly_stats"):
            self.assertRegex(self.sql, rf"CREATE MATERIALIZED VIEW {mv}")
            self.assertRegex(
                self.sql, rf"CREATE UNIQUE INDEX \w+\s+ON {mv}",
                f"{mv} needs a unique index for REFRESH CONCURRENTLY")

    def test_no_now_inside_generated_columns(self):
        # now()/current_date must never appear inside a STORED generated expression.
        for expr in re.findall(r"GENERATED ALWAYS AS \(([\s\S]*?)\) STORED", self.sql):
            self.assertNotRegex(expr.lower(), r"now\(\)|current_date",
                                "date-dependent expression in a generated column")


if __name__ == "__main__":
    unittest.main()
