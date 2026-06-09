"""Tests for the forecasting service."""
import unittest

from app.data.seed import build_seeded_repo
from app.services.forecasting import (
    _add_months,
    block_forecast,
    estate_forecast,
    forecast_series,
)


class TestHelpers(unittest.TestCase):
    def test_add_months_wraps_year(self):
        self.assertEqual(_add_months("2025-11-01", 1), "2025-12-01")
        self.assertEqual(_add_months("2025-12-01", 1), "2026-01-01")
        self.assertEqual(_add_months("2025-01-01", 13), "2026-02-01")


class TestForecastSeries(unittest.TestCase):
    def test_perfect_uptrend(self):
        # PSF rising 10/month -> slope ~10, near-perfect fit, projection rises.
        monthly = [{"month": _add_months("2024-01-01", i), "median_psf": 500 + 10 * i}
                   for i in range(12)]
        fc = forecast_series(monthly, horizon_months=6)
        self.assertAlmostEqual(fc["slope_per_month"], 10.0, places=1)
        self.assertGreater(fc["r_squared"], 0.99)
        self.assertGreater(fc["projected_psf"], fc["current_psf"])
        self.assertEqual(len(fc["projection"]), 6)

    def test_confidence_band_orders(self):
        monthly = [{"month": _add_months("2024-01-01", i), "median_psf": 500 + 10 * i}
                   for i in range(12)]
        fc = forecast_series(monthly)
        for p in fc["projection"]:
            self.assertLessEqual(p["lower"], p["psf"])
            self.assertLessEqual(p["psf"], p["upper"])

    def test_insufficient_data_returns_none(self):
        monthly = [{"month": "2024-01-01", "median_psf": 500},
                   {"month": "2024-02-01", "median_psf": 510}]
        self.assertIsNone(forecast_series(monthly))

    def test_ignores_none_points(self):
        monthly = [{"month": _add_months("2024-01-01", i),
                    "median_psf": None if i % 2 else 500 + i}
                   for i in range(12)]
        fc = forecast_series(monthly)
        self.assertIsNotNone(fc)


class TestBlockEstateForecast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=4, months=24)

    def test_estate_forecast(self):
        fc = estate_forecast(self.repo, 1)
        self.assertEqual(fc["scope"], "estate")
        self.assertIn("projection", fc)
        self.assertIn("Not financial advice", fc["disclaimer"])

    def test_block_forecast_or_none(self):
        bid = self.repo.blocks()[0].block_id
        fc = block_forecast(self.repo, bid, flat_type="4 ROOM", horizon_months=6)
        # May be None if a single flat type has too few months; if present, valid.
        if fc is not None:
            self.assertEqual(fc["scope"], "block")
            self.assertEqual(len(fc["projection"]), 6)

    def test_unknown_estate_none(self):
        self.assertIsNone(estate_forecast(self.repo, 999999))


if __name__ == "__main__":
    unittest.main()
