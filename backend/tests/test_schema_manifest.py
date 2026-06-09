"""Validate the schema manifest's internal geospatial-first invariants."""
import unittest

from app.schema import MANIFEST, SPATIAL_TABLES
from app.schema.manifest import (
    HDB_BLOCKS,
    HDB_TRANSACTIONS,
    SRID_SVY21,
    SRID_WGS84,
)


class TestManifestInvariants(unittest.TestCase):
    def test_table_names_unique(self):
        names = [t.name for t in MANIFEST]
        self.assertEqual(len(names), len(set(names)))

    def test_spatial_tables_have_dual_geometry(self):
        self.assertTrue(SPATIAL_TABLES)
        for t in SPATIAL_TABLES:
            cols = {c.name: c for c in t.columns}
            self.assertIn("geom", cols, f"{t.name} missing geom")
            self.assertIn("geom_svy21", cols, f"{t.name} missing geom_svy21")
            self.assertIn(str(SRID_WGS84), cols["geom"].pg_type,
                          f"{t.name}.geom must be SRID {SRID_WGS84}")
            self.assertIn(str(SRID_SVY21), cols["geom_svy21"].pg_type,
                          f"{t.name}.geom_svy21 must be SRID {SRID_SVY21}")
            self.assertTrue(cols["geom_svy21"].generated,
                            f"{t.name}.geom_svy21 must be generated")

    def test_blocks_have_no_date_dependent_generated_column(self):
        # remaining_lease_years depends on now() -> must NOT be a column.
        self.assertNotIn("remaining_lease_years", HDB_BLOCKS.column_names())

    def test_transactions_partitioned_by_month(self):
        self.assertEqual(HDB_TRANSACTIONS.partition_by, "transaction_month")
        # PK must include the partition key.
        self.assertIn("transaction_month", HDB_TRANSACTIONS.pk)

    def test_transactions_generated_columns(self):
        cols = {c.name: c for c in HDB_TRANSACTIONS.columns}
        self.assertTrue(cols["psf"].generated)
        self.assertTrue(cols["floor_area_sqft"].generated)

    def test_materialized_views_have_unique_index(self):
        mvs = [t for t in MANIFEST if t.is_materialized_view]
        self.assertTrue(mvs)
        for mv in mvs:
            self.assertTrue(mv.unique_index,
                            f"{mv.name} needs a unique index for CONCURRENTLY")
            for col in mv.unique_index:
                self.assertIn(col, mv.column_names())


if __name__ == "__main__":
    unittest.main()
