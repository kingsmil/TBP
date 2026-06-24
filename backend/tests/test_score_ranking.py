"""Tests for the Score Ranking engine."""
from __future__ import annotations

import unittest

from app.data.seed import build_seeded_repo
from app.services import score_ranking as sr
from app.services.commute.models import Destination
from app.core.geo import Point
from app.services.commute.provider import HeuristicCommuteProvider


def _repo():
    repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=12)
    return repo


class TestFieldRegistry(unittest.TestCase):
    def test_list_fields_includes_core_factors(self):
        keys = {f["key"] for f in sr.list_fields()}
        self.assertTrue(
            {"transport", "appreciation", "size", "convenience",
             "schools", "value", "lease", "amenities"}.issubset(keys))

    def test_amenities_marked_coming_soon(self):
        amenities = next(f for f in sr.list_fields() if f["key"] == "amenities")
        self.assertTrue(amenities["coming_soon"])

    def test_transport_needs_destinations(self):
        transport = next(f for f in sr.list_fields() if f["key"] == "transport")
        self.assertTrue(transport["needs_destinations"])


class TestRanking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = _repo()

    def test_ranks_blocks_best_first(self):
        out = sr.rank(self.repo, weights={"value": 50, "convenience": 50}, limit=10)
        self.assertGreater(out["count"], 0)
        scores = [r["overall_score"] for r in out["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        # rank is 1-indexed and contiguous
        self.assertEqual([r["rank"] for r in out["results"]],
                         list(range(1, len(out["results"]) + 1)))

    def test_breakdown_only_contains_weighted_fields(self):
        out = sr.rank(self.repo, weights={"value": 100}, limit=5)
        for r in out["results"]:
            self.assertEqual(set(r["breakdown"]), {"value"})

    def test_coming_soon_field_ignored(self):
        out = sr.rank(self.repo, weights={"amenities": 100}, limit=5)
        # amenities has no data and is coming-soon -> no active weights -> empty
        self.assertEqual(out["count"], 0)
        self.assertEqual(out["results"], [])

    def test_empty_weights_returns_no_results(self):
        out = sr.rank(self.repo, weights={}, limit=5)
        self.assertEqual(out["count"], 0)

    def test_unknown_field_ignored(self):
        out = sr.rank(self.repo, weights={"nonsense": 100, "value": 50}, limit=5)
        for r in out["results"]:
            self.assertEqual(set(r["breakdown"]), {"value"})

    def test_weights_change_order(self):
        by_value = sr.rank(self.repo, weights={"value": 100}, limit=50)["results"]
        by_size = sr.rank(self.repo, weights={"size": 100}, limit=50)["results"]
        value_order = [r["block_id"] for r in by_value]
        size_order = [r["block_id"] for r in by_size]
        # Different single-factor rankings should not be identical.
        self.assertNotEqual(value_order, size_order)

    def test_transport_uses_destinations_and_frequency(self):
        stations = list(self.repo.mrt_stations(status="operational"))
        self.assertTrue(stations)
        provider = HeuristicCommuteProvider(stations)
        dest = Destination(name="Work", point=Point(103.85, 1.29), visits_per_week=5)
        out = sr.rank(self.repo, weights={"transport": 100},
                      provider=provider, destinations=[dest], limit=10)
        self.assertGreater(out["count"], 0)
        for r in out["results"]:
            self.assertIn("transport", r["breakdown"])
            self.assertGreaterEqual(r["breakdown"]["transport"], 0.0)

    def test_transport_without_destinations_excluded(self):
        # Weighted but no destinations -> transport score None -> block excluded
        # when it's the only factor.
        out = sr.rank(self.repo, weights={"transport": 100}, limit=10)
        self.assertEqual(out["count"], 0)


if __name__ == "__main__":
    unittest.main()
