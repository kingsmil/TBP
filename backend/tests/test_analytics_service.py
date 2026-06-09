"""Tests for the analytics service."""
import unittest

from app.data.seed import build_seeded_repo
from app.services.analytics import (
    block_analytics,
    estate_analytics,
    estate_comparison,
    growth_pct,
    remaining_lease_years,
)


class TestHelpers(unittest.TestCase):
    def test_remaining_lease(self):
        self.assertEqual(remaining_lease_years(2012, current_year=2026), 85)
        # Never negative.
        self.assertEqual(remaining_lease_years(1900, current_year=2026), 0)

    def test_growth_pct(self):
        monthly = [{"median_psf": 100.0}, {"median_psf": 110.0}]
        self.assertAlmostEqual(growth_pct(monthly), 10.0)
        self.assertIsNone(growth_pct([{"median_psf": 100.0}]))
        self.assertIsNone(growth_pct([]))


class TestEstateAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=24)

    def test_unknown_estate_returns_none(self):
        self.assertIsNone(estate_analytics(self.repo, 99999))

    def test_estate_shapes(self):
        a = estate_analytics(self.repo, 1)
        self.assertEqual(a["scope"], "estate")
        for key in ("metrics", "psf_over_time", "volume_over_time",
                    "psf_by_flat_type", "psf_by_lease_age",
                    "price_vs_mrt_distance"):
            self.assertIn(key, a)

    def test_psf_series_sorted_by_month(self):
        a = estate_analytics(self.repo, 1)
        months = [r["month"] for r in a["psf_over_time"]]
        self.assertEqual(months, sorted(months))

    def test_volume_matches_series_length(self):
        a = estate_analytics(self.repo, 1)
        self.assertEqual(len(a["volume_over_time"]), len(a["psf_over_time"]))

    def test_growth_positive_for_upward_mock_trend(self):
        # Mock data has a gentle upward PSF trend, so growth should be > 0.
        a = estate_analytics(self.repo, 1)
        self.assertIsNotNone(a["metrics"]["growth_pct"])
        self.assertGreater(a["metrics"]["growth_pct"], 0)

    def test_price_vs_mrt_distance_populated(self):
        a = estate_analytics(self.repo, 1)
        self.assertTrue(a["price_vs_mrt_distance"])
        for r in a["price_vs_mrt_distance"]:
            self.assertIn("nearest_mrt_distance_m", r)
            self.assertIsNotNone(r["median_psf"])


class TestBlockAnalyticsAndComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=12)

    def test_block_analytics(self):
        bid = self.repo.blocks()[0].block_id
        a = block_analytics(self.repo, bid)
        self.assertEqual(a["scope"], "block")
        self.assertGreater(a["metrics"]["txn_count"], 0)
        self.assertIn("remaining_lease_years", a["metrics"])

    def test_block_unknown(self):
        self.assertIsNone(block_analytics(self.repo, 99999))

    def test_estate_comparison_covers_all_areas(self):
        rows = estate_comparison(self.repo)
        self.assertEqual(len(rows), len(self.repo.planning_areas()))
        # Sorted ascending by median psf.
        psfs = [r["median_psf"] for r in rows]
        self.assertEqual(psfs, sorted(psfs))


if __name__ == "__main__":
    unittest.main()
