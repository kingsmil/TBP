"""Tests for the estate comparison service."""
import unittest

from app.data.seed import build_seeded_repo
from app.services.comparison import compare_estates, estate_metrics, lease_profile


class TestComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=24)

    def test_estate_metrics_shape(self):
        m = estate_metrics(self.repo, 1)
        for key in ("name", "median_psf", "growth_pct", "txn_count",
                    "lease_profile", "accessibility"):
            self.assertIn(key, m)
        self.assertIn("combined_score", m["accessibility"])
        self.assertIn("avg_remaining_lease", m["lease_profile"])

    def test_estate_metrics_unknown_none(self):
        self.assertIsNone(estate_metrics(self.repo, 999999))

    def test_lease_profile_bounds(self):
        block_ids = [b.block_id for b in self.repo.blocks()
                     if b.planning_area_id == 1]
        lp = lease_profile(self.repo, block_ids, current_year=2026)
        self.assertLessEqual(lp["min_remaining_lease"], lp["avg_remaining_lease"])
        self.assertLessEqual(lp["avg_remaining_lease"], lp["max_remaining_lease"])
        self.assertGreaterEqual(lp["min_remaining_lease"], 0)

    def test_compare_all_estates(self):
        rows = compare_estates(self.repo)
        self.assertEqual(len(rows), len(self.repo.planning_areas()))

    def test_compare_sorted_by_accessibility_desc(self):
        rows = compare_estates(self.repo)
        scores = [r["accessibility"]["combined_score"] or 0.0 for r in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_compare_subset(self):
        rows = compare_estates(self.repo, planning_area_ids=[1, 2])
        ids = {r["planning_area_id"] for r in rows}
        self.assertEqual(ids, {1, 2})


if __name__ == "__main__":
    unittest.main()
