"""Tests for the Dream Home Finder."""
import unittest

from app.core.geo import Point
from app.data.seed import build_seeded_repo
from app.services.commute.models import Destination
from app.services.commute.provider import HeuristicCommuteProvider
from app.services.dream_home import DreamCriteria, _budget_fit, dream_home_finder


class TestBudgetFit(unittest.TestCase):
    def test_more_headroom_scores_higher(self):
        self.assertGreater(_budget_fit(400000, 600000), _budget_fit(560000, 600000))

    def test_none_inputs(self):
        self.assertIsNone(_budget_fit(None, 600000))
        self.assertIsNone(_budget_fit(400000, None))


class TestDreamHome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=12)
        cls.provider = HeuristicCommuteProvider(list(cls.repo.mrt_stations()))

    def test_returns_ranked_matches(self):
        res = dream_home_finder(self.repo, DreamCriteria(flat_type="4 ROOM", limit=10))
        self.assertGreater(res["match_count"], 0)
        self.assertLessEqual(len(res["results"]), 10)
        scores = [r["match_score"] for r in res["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_lease_hard_filter(self):
        res = dream_home_finder(self.repo, DreamCriteria(min_remaining_lease=80))
        for r in res["results"]:
            self.assertGreaterEqual(r["remaining_lease_years"], 80)

    def test_mrt_hard_filter(self):
        loose = dream_home_finder(self.repo, DreamCriteria())
        tight = dream_home_finder(self.repo, DreamCriteria(max_mrt_distance_m=500))
        self.assertLessEqual(tight["match_count"], loose["match_count"])

    def test_commute_component_included_with_destinations(self):
        crit = DreamCriteria(
            flat_type="4 ROOM",
            destinations=[Destination("Office", Point(103.945, 1.350), 5)],
            limit=5,
        )
        res = dream_home_finder(self.repo, crit, provider=self.provider)
        self.assertTrue(res["results"])
        self.assertIn("commute", res["results"][0]["components"])

    def test_recommended_estates_sorted(self):
        res = dream_home_finder(self.repo, DreamCriteria(flat_type="4 ROOM"))
        recs = res["recommended_estates"]
        scores = [r["avg_match_score"] for r in recs]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_match_score_bounded(self):
        res = dream_home_finder(self.repo, DreamCriteria(flat_type="4 ROOM"))
        for r in res["results"]:
            self.assertGreaterEqual(r["match_score"], 0.0)
            self.assertLessEqual(r["match_score"], 100.0)


if __name__ == "__main__":
    unittest.main()
