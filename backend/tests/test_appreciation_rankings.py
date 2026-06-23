"""Tests for the appreciation ranking analysis."""
from __future__ import annotations

import unittest

from app.analysis import appreciation_rankings as ar
from app.data.seed import build_seeded_repo


class TestCagr(unittest.TestCase):
    def test_cagr_basic_doubling(self):
        # 100 -> 200 over 10 years ≈ 7.18% CAGR.
        annual = {2016: 100.0, 2026: 200.0}
        out = ar._cagr(annual, ref_year=2026, years=10)
        self.assertIsNotNone(out)
        cagr_pct, psf_start, psf_end, y0, y1 = out
        self.assertAlmostEqual(cagr_pct, 7.18, delta=0.1)
        self.assertEqual((psf_start, psf_end, y0, y1), (100.0, 200.0, 2016, 2026))

    def test_cagr_window_excludes_old_years(self):
        annual = {2000: 50.0, 2024: 100.0, 2026: 110.0}
        out = ar._cagr(annual, ref_year=2026, years=10)  # window 2017-2026
        _, psf_start, _, y0, _ = out
        self.assertEqual((psf_start, y0), (100.0, 2024))  # 2000 excluded

    def test_cagr_needs_two_years(self):
        self.assertIsNone(ar._cagr({2026: 100.0}, ref_year=2026, years=10))

    def test_cagr_flat_is_zero(self):
        out = ar._cagr({2020: 100.0, 2026: 100.0}, ref_year=2026, years=10)
        self.assertEqual(out[0], 0.0)


class TestRankings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=120)

    def test_builds_block_and_region_rankings(self):
        blocks, regions = ar.build_rankings(self.repo, years=10)
        self.assertGreater(len(blocks), 0)
        self.assertGreater(len(regions), 0)

    def test_blocks_ranked_best_first_and_contiguous(self):
        blocks, _ = ar.build_rankings(self.repo, years=10)
        cagrs = [b.cagr_pct for b in blocks]
        self.assertEqual(cagrs, sorted(cagrs, reverse=True))
        self.assertEqual([b.rank for b in blocks], list(range(1, len(blocks) + 1)))

    def test_region_rank_contiguous(self):
        _, regions = ar.build_rankings(self.repo, years=10)
        self.assertEqual([r.rank for r in regions], list(range(1, len(regions) + 1)))

    def test_region_rank_within_area_assigned(self):
        blocks, _ = ar.build_rankings(self.repo, years=10)
        # Every block carries a positive within-region rank.
        self.assertTrue(all(b.region_rank >= 1 for b in blocks))

    def test_rows_carry_window_and_psf(self):
        blocks, _ = ar.build_rankings(self.repo, years=10)
        b = blocks[0]
        self.assertGreaterEqual(b.year_end, b.year_start)
        self.assertGreater(b.median_psf_end, 0)
        self.assertGreaterEqual(b.txn_count, ar.BLOCK_MIN_TXNS)


class TestScoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=120)

    def test_cagr_only_default_has_no_scores(self):
        # Default build is fast CAGR-only (no composite score).
        blocks, _ = ar.build_rankings(self.repo, years=10)
        self.assertTrue(all(b.appreciation_score is None for b in blocks))

    def test_with_score_only_scores_top_n_per_region(self):
        blocks, _ = ar.build_rankings(self.repo, years=10, with_score=True, score_top_n=2)
        scored = [b for b in blocks if b.appreciation_score is not None]
        self.assertGreater(len(scored), 0)
        self.assertTrue(all(b.region_rank <= 2 for b in scored))

    def test_top_n_bounds_scored_count(self):
        few, _ = ar.build_rankings(self.repo, years=10, with_score=True, score_top_n=2)
        more, _ = ar.build_rankings(self.repo, years=10, with_score=True, score_top_n=None)
        n_few = sum(b.appreciation_score is not None for b in few)
        n_all = sum(b.appreciation_score is not None for b in more)
        self.assertGreater(n_few, 0)
        self.assertLessEqual(n_few, n_all)

    def test_region_score_present_when_blocks_scored(self):
        blocks, regions = ar.build_rankings(self.repo, years=10, with_score=True, score_top_n=5)
        self.assertTrue(any(r.appreciation_score is not None for r in regions))


if __name__ == "__main__":
    unittest.main()
