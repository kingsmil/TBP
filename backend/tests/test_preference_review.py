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


def _q(field):
    return {"event": "clarifying_question", "field": field, "question": "x"}


class TestPreferenceReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.homeos.wiring import setup
        setup()

    def _review(self, query_dict, prefs, count=3, pipeline=None):
        from app.homeos.pipeline import _preference_review
        return _preference_review(query_dict, prefs, count, pipeline or [])

    def test_all_set_returns_none(self):
        query_dict = {
            "flat_type": "4 ROOM", "max_price": 400000.0, "town": "TAMPINES",
            "max_mrt_distance_m": 600.0, "min_schools_within_1km": 2,
        }
        q, field = self._review(query_dict, {"risk_tolerance": "medium"})
        self.assertIsNone(q)
        self.assertIsNone(field)

    def test_lists_exactly_the_missing_dimensions(self):
        q, field = self._review({"flat_type": "4 ROOM", "max_price": 400000.0}, {})
        self.assertEqual(field, "preference_review")
        self.assertIn("MRT importance", q)
        self.assertIn("Primary schools", q)
        self.assertIn("town or estate", q)
        self.assertIn("Risk tolerance", q)
        self.assertNotIn("budget ceiling", q)
        self.assertNotIn("Flat type", q)
        self.assertIn("3 blocks", q)
        self.assertIn("proceed", q)

    def test_asked_history_suppresses_dimensions(self):
        pipeline = [_q("commute_priority"), _q("school_priority"), _q("town")]
        q, field = self._review({"flat_type": "4 ROOM", "max_price": 400000.0}, {},
                                pipeline=pipeline)
        self.assertEqual(field, "preference_review")
        self.assertNotIn("MRT importance", q)
        self.assertNotIn("Primary schools", q)
        self.assertNotIn("town or estate", q)
        self.assertIn("Risk tolerance", q)

    def test_fires_once_per_case(self):
        q, field = self._review({"flat_type": "4 ROOM"}, {},
                                pipeline=[_q("preference_review")])
        self.assertIsNone(q)
        self.assertIsNone(field)

    def test_question_includes_set_params_summary(self):
        q, _ = self._review({"flat_type": "4 ROOM", "max_price": 400000.0}, {})
        self.assertIn("flat_type=4 ROOM", q)
        self.assertIn("max_price=400000.0", q)


if __name__ == "__main__":
    unittest.main()
