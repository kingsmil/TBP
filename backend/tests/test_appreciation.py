"""Tests for the appreciation engine."""
import unittest

from app.data.seed import build_seeded_repo
from app.services.appreciation import _growth_score, appreciation


class TestGrowthScore(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(_growth_score(-10), 0.0)   # below floor
        self.assertEqual(_growth_score(20), 100.0)  # above cap
        self.assertIsNone(_growth_score(None))

    def test_monotonic(self):
        self.assertGreater(_growth_score(10), _growth_score(0))


class TestAppreciation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=5, months=24)
        cls.bid = cls.repo.blocks()[0].block_id

    def test_shape_and_bounds(self):
        a = appreciation(self.repo, self.bid)
        self.assertIn("appreciation_score", a)
        self.assertIn("confidence_level", a)
        self.assertIn("risk_level", a)
        self.assertIn("disclaimer", a)
        self.assertGreaterEqual(a["appreciation_score"], 0.0)
        self.assertLessEqual(a["appreciation_score"], 100.0)

    def test_levels_valid(self):
        a = appreciation(self.repo, self.bid)
        self.assertIn(a["confidence_level"], {"low", "medium", "high"})
        self.assertIn(a["risk_level"], {"low", "medium", "high"})

    def test_disclaimer_present(self):
        a = appreciation(self.repo, self.bid)
        self.assertIn("Not financial advice", a["disclaimer"])

    def test_more_data_higher_confidence(self):
        # 24 months x 3 txns/month = 72 transactions/block (>= 60 => high).
        big, _ = build_seeded_repo(seed=1, blocks_per_area=2, months=24,
                                   txns_per_block_month=3)
        bid = big.blocks()[0].block_id
        self.assertEqual(appreciation(big, bid)["confidence_level"], "high")

    def test_unknown_block_none(self):
        self.assertIsNone(appreciation(self.repo, 999999))

    def test_lease_drives_score(self):
        # Among blocks, a longer remaining lease should not lower appreciation
        # all else being roughly comparable; check the factor is present.
        a = appreciation(self.repo, self.bid)
        self.assertIn("lease", a["factors"])
        self.assertGreaterEqual(a["factors"]["lease"], 0.0)


if __name__ == "__main__":
    unittest.main()
