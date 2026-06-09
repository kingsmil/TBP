"""Tests for the recommendation engine."""
import unittest

from app.core.geo import Point
from app.data.seed import build_seeded_repo
from app.services.commute.models import Destination
from app.services.commute.provider import HeuristicCommuteProvider
from app.services.recommendation import _reasons, recommend


class TestReasons(unittest.TestCase):
    def test_picks_strong_factors(self):
        r = _reasons({"transport": 80, "schools": 70, "affordability": 30}, 65)
        self.assertIn("strong transport access", r)
        self.assertIn("good school access", r)
        self.assertIn("solid appreciation potential", r)
        self.assertNotIn("good value for money", r)  # below 60

    def test_fallback_when_nothing_strong(self):
        self.assertEqual(_reasons({"transport": 10}, 10),
                         ["balanced overall profile"])


class TestRecommend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=12)
        cls.provider = HeuristicCommuteProvider(list(cls.repo.mrt_stations()))

    def test_ranked_with_reasons(self):
        res = recommend(self.repo, limit=10)
        self.assertGreaterEqual(res["count"], 1)
        self.assertLessEqual(len(res["results"]), 10)
        scores = [r["overall_score"] for r in res["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(res["results"][0]["reasons"])

    def test_scores_bounded(self):
        res = recommend(self.repo)
        for r in res["results"]:
            self.assertGreaterEqual(r["overall_score"], 0.0)
            self.assertLessEqual(r["overall_score"], 100.0)

    def test_with_commute_destinations(self):
        dests = [Destination("Office", Point(103.945, 1.350), 5)]
        res = recommend(self.repo, provider=self.provider, destinations=dests, limit=5)
        self.assertTrue(res["results"])

    def test_recommended_estates_sorted(self):
        res = recommend(self.repo)
        scores = [r["avg_score"] for r in res["recommended_estates"]]
        self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()
