"""Tests for the commute optimizer + heatmap."""
import unittest

from app.core.geo import Point
from app.data.seed import build_seeded_repo
from app.services.commute.models import Destination
from app.services.commute.optimizer import (
    commute_burden,
    commute_heatmap,
    commute_score,
    optimize_commute,
    score_band,
)
from app.services.commute.provider import HeuristicCommuteProvider


class TestBurdenAndScore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=5, months=6)
        cls.provider = HeuristicCommuteProvider(list(cls.repo.mrt_stations()))
        # Office in Tampines region.
        cls.office = Destination("Office", Point(103.945, 1.350), visits_per_week=5)

    def test_burden_scales_with_visits(self):
        origin = Point(103.700, 1.350)
        one = commute_burden(self.provider, origin,
                             [Destination("o", self.office.point, 1)])
        five = commute_burden(self.provider, origin,
                              [Destination("o", self.office.point, 5)])
        self.assertAlmostEqual(five["weekly_minutes"], one["weekly_minutes"] * 5, places=1)

    def test_monthly_is_weekly_times_factor(self):
        origin = Point(103.700, 1.350)
        b = commute_burden(self.provider, origin, [self.office])
        self.assertAlmostEqual(b["monthly_minutes"],
                               b["weekly_minutes"] * 52 / 12, places=1)

    def test_commute_score_bounds_and_direction(self):
        self.assertEqual(commute_score(0), 100.0)
        self.assertEqual(commute_score(100000), 0.0)
        self.assertGreater(commute_score(200), commute_score(1000))

    def test_score_band(self):
        self.assertEqual(score_band(90), "green")
        self.assertEqual(score_band(50), "yellow")
        self.assertEqual(score_band(10), "red")


class TestOptimize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=5, months=6)
        cls.provider = HeuristicCommuteProvider(list(cls.repo.mrt_stations()))
        cls.dest = [Destination("Office", Point(103.945, 1.350), 5)]

    def test_optimize_sorted_by_score_desc(self):
        res = optimize_commute(self.repo, self.provider, self.dest)
        scores = [r["commute_score"] for r in res]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_optimize_limit(self):
        res = optimize_commute(self.repo, self.provider, self.dest, limit=3)
        self.assertEqual(len(res), 3)

    def test_blocks_near_office_score_higher(self):
        res = optimize_commute(self.repo, self.provider, self.dest,
                               limit=len(self.repo.blocks()))
        by_id = {r["block_id"]: r for r in res}
        tampines = [r for r in res if r["town"] == "TAMPINES"]
        jurong = [r for r in res if r["town"] == "JURONG WEST"]
        self.assertTrue(tampines and jurong)
        avg_tampines = sum(r["commute_score"] for r in tampines) / len(tampines)
        avg_jurong = sum(r["commute_score"] for r in jurong) / len(jurong)
        # Office is in Tampines, so Tampines blocks should fit better than Jurong.
        self.assertGreater(avg_tampines, avg_jurong)
        self.assertTrue(by_id)  # sanity

    def test_heatmap_shape_covers_all_blocks(self):
        hm = commute_heatmap(self.repo, self.provider, self.dest)
        self.assertEqual(len(hm), len(self.repo.blocks()))
        for r in hm:
            self.assertIn(r["band"], {"green", "yellow", "red"})


if __name__ == "__main__":
    unittest.main()
