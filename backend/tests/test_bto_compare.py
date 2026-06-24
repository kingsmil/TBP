"""Tests for BTO-vs-resale comparison helpers."""
from __future__ import annotations

import unittest

from app.services.bto_compare import _norm_room, _cagr, _resale_index
from app.data.seed import build_seeded_repo


class TestNorm(unittest.TestCase):
    def test_room_normalisation_matches_bto_and_resale(self):
        self.assertEqual(_norm_room("4-room"), "4 ROOM")
        self.assertEqual(_norm_room("4 ROOM"), "4 ROOM")
        self.assertEqual(_norm_room("5-Room"), "5 ROOM")
        self.assertEqual(_norm_room("EXECUTIVE"), "EXECUTIVE")
        self.assertEqual(_norm_room(None), "")


class TestCagr(unittest.TestCase):
    def test_cagr_doubling_over_decade(self):
        self.assertAlmostEqual(_cagr({2016: 100.0, 2026: 200.0}), 7.18, delta=0.1)

    def test_cagr_needs_two_years(self):
        self.assertIsNone(_cagr({2026: 100.0}))


class TestResaleIndex(unittest.TestCase):
    def test_index_groups_by_town_and_room(self):
        repo, _ = build_seeded_repo(seed=42, blocks_per_area=5, months=12)
        idx = _resale_index(repo)
        self.assertGreater(len(idx), 0)
        # keys are (TOWN_UPPER, "N ROOM"); values carry a median + count.
        for (town, room), v in idx.items():
            self.assertEqual(town, town.upper())
            self.assertIn("median_price", v)
            self.assertGreaterEqual(v["count"], 1)
            break


if __name__ == "__main__":
    unittest.main()
