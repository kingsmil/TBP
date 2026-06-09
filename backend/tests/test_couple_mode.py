"""Tests for couple mode (combined burden + fairness)."""
import unittest

from app.core.geo import Point
from app.data.seed import build_seeded_repo
from app.services.commute.couple import (
    couple_optimize,
    fairness_score,
    recommended_estates,
)
from app.services.commute.models import Destination, Person
from app.services.commute.provider import HeuristicCommuteProvider


class TestFairness(unittest.TestCase):
    def test_balanced_is_100(self):
        self.assertEqual(fairness_score(300, 300), 100.0)

    def test_zero_is_100(self):
        self.assertEqual(fairness_score(0, 0), 100.0)

    def test_lopsided_is_lower(self):
        self.assertLess(fairness_score(100, 900), fairness_score(400, 600))

    def test_symmetric(self):
        self.assertEqual(fairness_score(200, 800), fairness_score(800, 200))


class TestCoupleOptimize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=5, months=6)
        cls.provider = HeuristicCommuteProvider(list(cls.repo.mrt_stations()))
        cls.a = Person("alice", (Destination("A-office", Point(103.945, 1.350), 5),))
        cls.b = Person("bob", (Destination("B-office", Point(103.710, 1.350), 5),))

    def test_rows_cover_blocks_and_sorted(self):
        rows = couple_optimize(self.repo, self.provider, self.a, self.b,
                               limit=len(self.repo.blocks()))
        self.assertEqual(len(rows), len(self.repo.blocks()))
        scores = [r["overall_score"] for r in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_row_has_person_columns(self):
        rows = couple_optimize(self.repo, self.provider, self.a, self.b, limit=1)
        r = rows[0]
        self.assertIn("alice_weekly_minutes", r)
        self.assertIn("bob_weekly_minutes", r)
        self.assertIn("fairness_score", r)

    def test_overall_score_bounded(self):
        rows = couple_optimize(self.repo, self.provider, self.a, self.b)
        for r in rows:
            self.assertGreaterEqual(r["overall_score"], 0.0)
            self.assertLessEqual(r["overall_score"], 100.0)

    def test_recommended_estates(self):
        rows = couple_optimize(self.repo, self.provider, self.a, self.b,
                               limit=len(self.repo.blocks()))
        recs = recommended_estates(rows, top_n=2)
        self.assertLessEqual(len(recs), 2)
        scores = [r["avg_overall_score"] for r in recs]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_invalid_weights_raise(self):
        with self.assertRaises(ValueError):
            couple_optimize(self.repo, self.provider, self.a, self.b,
                            weights={"commute": 0, "fairness": 0})


if __name__ == "__main__":
    unittest.main()
