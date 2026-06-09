"""Tests for the HDB filter/search service."""
import unittest

from app.core.models import SearchQuery
from app.data.seed import build_seeded_repo
from app.services.search import search_blocks


class TestSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=12)

    def test_no_filters_returns_all_blocks(self):
        res = search_blocks(self.repo, SearchQuery())
        self.assertEqual(len(res), len(self.repo.blocks()))

    def test_town_filter(self):
        res = search_blocks(self.repo, SearchQuery(town="TAMPINES"))
        self.assertTrue(res)
        self.assertTrue(all(r["town"] == "TAMPINES" for r in res))

    def test_planning_area_filter(self):
        res = search_blocks(self.repo, SearchQuery(planning_area_id=1))
        self.assertTrue(all(r["planning_area_id"] == 1 for r in res))

    def test_bbox_filter_limits_results(self):
        all_res = search_blocks(self.repo, SearchQuery())
        # Tampines rectangle only.
        bbox = (103.93, 1.34, 103.97, 1.36)
        res = search_blocks(self.repo, SearchQuery(bbox=bbox))
        self.assertTrue(res)
        self.assertLess(len(res), len(all_res))
        for r in res:
            self.assertTrue(103.93 <= r["lon"] <= 103.97)
            self.assertTrue(1.34 <= r["lat"] <= 1.36)

    def test_proximity_filter_monotonic(self):
        loose = search_blocks(self.repo, SearchQuery(max_mrt_distance_m=100000))
        tight = search_blocks(self.repo, SearchQuery(max_mrt_distance_m=500))
        self.assertLessEqual(len(tight), len(loose))
        for r in tight:
            self.assertLessEqual(r["nearest_mrt_distance_m"], 500)

    def test_flat_type_filter_and_stats(self):
        res = search_blocks(self.repo, SearchQuery(flat_type="4 ROOM"))
        self.assertTrue(res)
        for r in res:
            self.assertGreater(r["txn_count"], 0)
            self.assertIsNotNone(r["median_psf"])

    def test_psf_band(self):
        lo, hi = 500, 650
        res = search_blocks(self.repo, SearchQuery(min_psf=lo, max_psf=hi))
        for r in res:
            self.assertGreaterEqual(r["median_psf"], lo)
            self.assertLessEqual(r["median_psf"], hi)

    def test_results_sorted_by_median_psf(self):
        res = search_blocks(self.repo, SearchQuery(flat_type="4 ROOM"))
        psfs = [r["median_psf"] for r in res]
        self.assertEqual(psfs, sorted(psfs))

    def test_limit_applied(self):
        res = search_blocks(self.repo, SearchQuery(limit=5))
        self.assertEqual(len(res), 5)

    def test_schools_within_filter(self):
        res = search_blocks(self.repo, SearchQuery(min_schools_within_1km=1))
        for r in res:
            self.assertGreaterEqual(r["schools_within_1km"], 1)


if __name__ == "__main__":
    unittest.main()
