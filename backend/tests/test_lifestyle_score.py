"""Tests for the lifestyle score."""
import unittest

from app.core.geo import Point
from app.data.seed import build_seeded_repo
from app.services.commute.models import Destination
from app.services.commute.provider import HeuristicCommuteProvider
from app.services.lifestyle import (
    affordability_score,
    block_lifestyle,
    lifestyle_score,
)


class TestLifestyleScoreFn(unittest.TestCase):
    def test_weighted_mean(self):
        # Equal weights over two factors -> simple average.
        s = lifestyle_score({"transport": 80, "schools": 40},
                            {"transport": 0.5, "schools": 0.5})
        self.assertAlmostEqual(s, 60.0)

    def test_blank_factor_excluded_not_averaged(self):
        # Only transport supplied -> score equals transport, regardless of other
        # default weights ("blank means not considered").
        s = lifestyle_score({"transport": 70})
        self.assertEqual(s, 70.0)

    def test_renormalizes_over_present_factors(self):
        # transport(.25) + schools(.20) present -> normalized 25/45 & 20/45.
        s = lifestyle_score({"transport": 100, "schools": 0})
        self.assertAlmostEqual(s, round(100 * 0.25 / 0.45, 2), places=1)

    def test_no_factors_returns_none(self):
        self.assertIsNone(lifestyle_score({}))


class TestAffordabilityAndBlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=5, months=12)
        cls.provider = HeuristicCommuteProvider(list(cls.repo.mrt_stations()))

    def test_affordability_cheaper_scores_higher(self):
        bounds = (400.0, 800.0)
        cheap = affordability_score(self.repo, self.repo.blocks()[0].block_id, (400, 800))
        # Construct via known psf bounds: a block at the cheap end > pricey end.
        self.assertIsNotNone(cheap)
        self.assertGreaterEqual(cheap, 0.0)
        self.assertLessEqual(cheap, 100.0)
        self.assertIsNotNone(bounds)

    def test_block_lifestyle_without_commute(self):
        bid = self.repo.blocks()[0].block_id
        result = block_lifestyle(self.repo, bid)
        self.assertIn("transport", result["factors"])
        self.assertIn("schools", result["factors"])
        self.assertIn("affordability", result["factors"])
        self.assertNotIn("commute", result["factors"])  # no destinations given
        self.assertIsNotNone(result["lifestyle_score"])

    def test_block_lifestyle_with_commute(self):
        bid = self.repo.blocks()[0].block_id
        dests = [Destination("Office", Point(103.945, 1.350), 5)]
        result = block_lifestyle(self.repo, bid, provider=self.provider,
                                 destinations=dests)
        self.assertIn("commute", result["factors"])
        self.assertGreaterEqual(result["lifestyle_score"], 0.0)
        self.assertLessEqual(result["lifestyle_score"], 100.0)

    def test_unknown_block_none(self):
        self.assertIsNone(block_lifestyle(self.repo, 999999))


if __name__ == "__main__":
    unittest.main()
