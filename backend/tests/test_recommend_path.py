"""Tests for the BTO-vs-Resale recommendation engine."""
from __future__ import annotations

import unittest

from app.services.recommend_path import recommend, questions, QUESTIONS


class TestQuestions(unittest.TestCase):
    def test_schema_shape(self):
        qs = questions()
        self.assertEqual(len(qs), len(QUESTIONS))
        for q in qs:
            self.assertIn("id", q)
            self.assertIn("label", q)
            self.assertTrue(q["options"])
            self.assertIn("value", q["options"][0])


class TestRecommend(unittest.TestCase):
    def test_needs_to_move_soon_is_resale(self):
        out = recommend({"timeline": "soon", "certainty": "certain", "priority": "speed"})
        self.assertEqual(out["recommendation"], "resale")
        self.assertTrue(out["reasons"])

    def test_cheap_flexible_first_timer_is_bto(self):
        out = recommend({
            "timeline": "flexible", "budget": "tight", "location": "open",
            "eligibility": "first_fam", "certainty": "ok_ballot", "priority": "price",
        })
        self.assertEqual(out["recommendation"], "bto")
        self.assertEqual(out["confidence"], "strong")

    def test_balanced_is_either(self):
        out = recommend({"location": "specific", "budget": "tight"})  # +2 resale, +2 bto
        self.assertEqual(out["recommendation"], "either")

    def test_no_answers_is_either_with_fallback_reason(self):
        out = recommend({})
        self.assertEqual(out["recommendation"], "either")
        self.assertTrue(out["reasons"])

    def test_reasons_match_recommended_side(self):
        out = recommend({"timeline": "soon", "priority": "speed", "certainty": "certain"})
        # All reasons should support resale (the recommendation), not BTO.
        joined = " ".join(out["reasons"]).lower()
        self.assertIn("resale", joined)
        self.assertNotIn("subsidised", joined)  # a BTO-only reason

    def test_score_net_sign(self):
        out = recommend({"timeline": "flexible", "priority": "price"})  # bto-leaning
        self.assertGreater(out["score"]["net"], 0)


if __name__ == "__main__":
    unittest.main()
