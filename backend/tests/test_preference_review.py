"""Unit tests for catalogue-declared dimensions and the preference review gate."""
import unittest


class TestCatalogueDimensions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.homeos.wiring import setup
        setup()
        import app.homeos.wiring as wiring_mod
        cls.tr = wiring_mod.tool_repository

    def test_catalogue_declares_the_six_dimensions(self):
        dims = {d.field: d for d in self.tr.review_dimensions()}
        self.assertEqual(
            set(dims),
            {"flat_type", "max_price", "town",
             "commute_priority", "school_priority", "risk_tolerance"},
        )

    def test_search_dims_carry_query_keys(self):
        dims = {d.field: d for d in self.tr.review_dimensions()}
        self.assertEqual(dims["flat_type"].query_key, "flat_type")
        self.assertEqual(dims["max_price"].query_key, "max_price")
        self.assertEqual(dims["town"].query_key, "town")
        self.assertEqual(dims["commute_priority"].query_key, "max_mrt_distance_m")
        self.assertEqual(dims["school_priority"].query_key, "min_schools_within_1km")

    def test_risk_tolerance_uses_default_heuristic(self):
        dims = {d.field: d for d in self.tr.review_dimensions()}
        self.assertIsNone(dims["risk_tolerance"].query_key)
        self.assertEqual(dims["risk_tolerance"].default, "low")


if __name__ == "__main__":
    unittest.main()
