"""Unit tests for catalogue-declared dimensions and the preference review gate."""
import unittest


class TestCatalogueDimensions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.homeos.wiring import setup
        setup()
        import app.homeos.wiring as wiring_mod
        cls.tr = wiring_mod.tool_repository

    def test_catalogue_declares_the_eight_dimensions(self):
        dims = {d.field: d for d in self.tr.review_dimensions()}
        self.assertEqual(
            set(dims),
            {"flat_type", "max_price", "town",
             "commute_priority", "school_priority", "risk_tolerance",
             "work_locations", "bus_reliance"},
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

    def test_commute_and_bus_dimensions_use_preference_defaults(self):
        dims = {d.field: d for d in self.tr.review_dimensions()}
        self.assertIsNone(dims["work_locations"].query_key)
        self.assertEqual(dims["work_locations"].default, [])
        self.assertIsNone(dims["bus_reliance"].query_key)
        self.assertEqual(dims["bus_reliance"].default, "low")

    def test_pref_dimension_has_question_field(self):
        from app.homeos.framework.spec import PrefDimension
        # with explicit question
        d = PrefDimension(field="x", prompt="p", question="Is this right?")
        self.assertEqual(d.question, "Is this right?")
        # default is empty string
        d2 = PrefDimension(field="x", prompt="p")
        self.assertEqual(d2.question, "")

    def test_all_dims_have_question_strings(self):
        dims = {d.field: d for d in self.tr.review_dimensions()}
        for field, dim in dims.items():
            self.assertNotEqual(
                dim.question, "",
                f"PrefDimension '{field}' has no question string — add question= to its declaration",
            )


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
        q, field = self._review(
            query_dict,
            {"risk_tolerance": "medium", "work_locations": ["Raffles Place"], "bus_reliance": "high"},
        )
        self.assertIsNone(q)
        self.assertIsNone(field)

    def test_returns_one_question_with_specific_dim_field(self):
        q, field = self._review({"flat_type": "4 ROOM", "max_price": 400000.0}, {})
        # Returns a single question for one specific dim (not the old "preference_review" catch-all)
        self.assertIsNotNone(q)
        self.assertIsNotNone(field)
        self.assertNotEqual(field, "preference_review")
        self.assertIn(field, {"commute_priority", "school_priority", "town",
                               "work_locations", "bus_reliance", "risk_tolerance"})
        # No bullet list
        self.assertNotIn("•", q)
        self.assertNotIn("haven't told me", q)
        self.assertNotIn("Answer any of these", q)

    def test_question_uses_dim_question_string(self):
        # Only risk_tolerance missing
        query_dict = {
            "flat_type": "4 ROOM", "max_price": 400000.0, "town": "TAMPINES",
            "max_mrt_distance_m": 600.0, "min_schools_within_1km": 2,
        }
        q, field = self._review(
            query_dict,
            {"work_locations": ["Raffles Place"], "bus_reliance": "high"},
        )
        self.assertEqual(field, "risk_tolerance")
        self.assertIn("investment risk", q)

    def test_preamble_uses_count_low(self):
        query_dict = {
            "flat_type": "4 ROOM", "max_price": 400000.0, "town": "TAMPINES",
            "max_mrt_distance_m": 600.0, "min_schools_within_1km": 2,
        }
        q, _ = self._review(query_dict, {"work_locations": ["Raffles Place"], "bus_reliance": "high"}, count=3)
        self.assertIn("3 blocks", q)

    def test_preamble_uses_still_for_high_count(self):
        query_dict = {
            "flat_type": "4 ROOM", "max_price": 400000.0, "town": "TAMPINES",
            "max_mrt_distance_m": 600.0, "min_schools_within_1km": 2,
        }
        q, _ = self._review(query_dict, {"work_locations": ["Raffles Place"], "bus_reliance": "high"}, count=15)
        self.assertIn("15 options", q)

    def test_asked_dims_are_skipped(self):
        pipeline = [_q("commute_priority"), _q("school_priority"), _q("town")]
        q, field = self._review({"flat_type": "4 ROOM", "max_price": 400000.0}, {},
                                pipeline=pipeline)
        self.assertIsNotNone(q)
        self.assertNotEqual(field, "preference_review")
        self.assertIn(field, {"work_locations", "bus_reliance", "risk_tolerance"})

    def test_all_dims_asked_returns_none(self):
        all_fields = ["flat_type", "max_price", "town", "commute_priority",
                      "school_priority", "risk_tolerance", "work_locations", "bus_reliance"]
        pipeline = [_q(f) for f in all_fields]
        q, field = self._review({}, {}, pipeline=pipeline)
        self.assertIsNone(q)
        self.assertIsNone(field)

    def test_query_key_in_dict_skips_dim(self):
        # max_mrt_distance_m in query_dict → commute_priority skipped
        q, field = self._review(
            {"flat_type": "4 ROOM", "max_price": 400000.0, "max_mrt_distance_m": 600.0}, {}
        )
        self.assertNotEqual(field, "commute_priority")


if __name__ == "__main__":
    unittest.main()
