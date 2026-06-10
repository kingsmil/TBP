"""Tests for commute providers (heuristic behaviour + OneMap parsing)."""
import os
import unittest
from unittest.mock import patch

from app.core.geo import Point
from app.data.seed import build_seeded_repo
from app.services.commute.onemap import OneMapCommuteProvider
from app.services.commute.provider import HeuristicCommuteProvider


class TestHeuristicProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo, _ = build_seeded_repo(seed=42, blocks_per_area=4, months=6)
        cls.provider = HeuristicCommuteProvider(list(repo.mrt_stations()))
        cls.blocks = list(repo.blocks())

    def test_walk_only_for_short_distance(self):
        o = Point(103.9400, 1.3500)
        d = Point(103.9405, 1.3502)  # ~60 m away
        r = self.provider.route(o, d)
        self.assertEqual(r.mode, "walk")
        self.assertEqual(r.transfers, 0)
        self.assertGreater(r.total_minutes, 0)

    def test_pt_for_long_distance(self):
        o = Point(103.700, 1.350)   # west
        d = Point(103.960, 1.350)   # east
        r = self.provider.route(o, d, mode="pt")
        self.assertEqual(r.mode, "pt")
        self.assertGreater(r.total_minutes, 0)

    def test_farther_destination_takes_longer(self):
        o = Point(103.700, 1.350)
        near = Point(103.730, 1.350)
        far = Point(103.960, 1.350)
        t_near = self.provider.route(o, near).total_minutes
        t_far = self.provider.route(o, far).total_minutes
        self.assertGreater(t_far, t_near)

    def test_drive_mode(self):
        o = Point(103.700, 1.350)
        d = Point(103.960, 1.350)
        r = self.provider.route(o, d, mode="drive")
        self.assertEqual(r.mode, "drive")
        self.assertEqual(r.walk_minutes, 0.0)


class TestOneMapParsing(unittest.TestCase):
    def test_parse_itinerary(self):
        payload = {"plan": {"itineraries": [
            {"duration": 1800, "walkTime": 300, "transfers": 1, "walkDistance": 420.0}
        ]}}
        r = OneMapCommuteProvider._parse(payload, Point(0, 0), Point(0, 0), "pt")
        self.assertEqual(r.total_minutes, 30.0)
        self.assertEqual(r.walk_minutes, 5.0)
        self.assertEqual(r.transfers, 1)
        self.assertEqual(r.distance_m, 420.0)

    def test_parse_empty_raises(self):
        with self.assertRaises(ValueError):
            OneMapCommuteProvider._parse({"plan": {"itineraries": []}},
                                         Point(0, 0), Point(0, 0), "pt")

    def test_requires_token(self):
        # Ensure ONEMAP_TOKEN is absent from the environment so the constructor
        # cannot fall back to it, regardless of test ordering.
        env_without_token = {k: v for k, v in os.environ.items() if k != "ONEMAP_TOKEN"}
        with patch.dict(os.environ, env_without_token, clear=True):
            with self.assertRaises(RuntimeError):
                OneMapCommuteProvider(token="")


if __name__ == "__main__":
    unittest.main()
