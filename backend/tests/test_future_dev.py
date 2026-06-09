"""Tests for future MRT + future supply analysis."""
import unittest

from app.data.seed import build_seeded_repo
from app.services.future_dev import future_mrt, future_supply


class TestFutureDev(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=5, months=6)
        cls.bid = cls.repo.blocks()[0].block_id

    def test_future_mrt_shape(self):
        fm = future_mrt(self.repo, self.bid)
        for key in ("distance_m", "opening_year", "future_transport_growth_score",
                    "station_name"):
            self.assertIn(key, fm)
        self.assertGreaterEqual(fm["future_transport_growth_score"], 0.0)
        self.assertLessEqual(fm["future_transport_growth_score"], 100.0)

    def test_future_mrt_unknown_none(self):
        self.assertIsNone(future_mrt(self.repo, 999999))

    def test_future_supply_counts_nearby(self):
        fs = future_supply(self.repo, self.bid, radius_m=3000)
        self.assertGreaterEqual(fs["future_bto_count"], 1)  # each area has a BTO
        self.assertEqual(len(fs["projects"]), fs["future_bto_count"])
        self.assertIn(fs["supply_risk_level"], {"low", "medium", "high"})

    def test_future_supply_radius_zero(self):
        fs = future_supply(self.repo, self.bid, radius_m=1.0)
        self.assertEqual(fs["future_bto_count"], 0)
        self.assertEqual(fs["supply_pressure_pct"], 0.0)

    def test_future_supply_unknown_none(self):
        self.assertIsNone(future_supply(self.repo, 999999))


if __name__ == "__main__":
    unittest.main()
