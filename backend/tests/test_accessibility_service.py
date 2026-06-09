"""Tests for the accessibility scoring service."""
import unittest

from app.core.models import BlockProximity
from app.data.seed import build_seeded_repo
from app.services.accessibility import (
    block_accessibility,
    bus_score,
    combined_score,
    estate_accessibility,
    linear_decay,
    mrt_score,
    school_score,
)


def prox(**kw) -> BlockProximity:
    base = dict(block_id=1, nearest_mrt_distance_m=300,
                nearest_future_mrt_distance_m=800, nearest_bus_distance_m=150,
                schools_within_1km=2, schools_within_2km=4,
                bus_stops_within_400m=3)
    base.update(kw)
    return BlockProximity(**base)


class TestLinearDecay(unittest.TestCase):
    def test_edges_and_midpoint(self):
        self.assertEqual(linear_decay(100, 200, 2000), 100.0)   # better than best
        self.assertEqual(linear_decay(200, 200, 2000), 100.0)
        self.assertEqual(linear_decay(2000, 200, 2000), 0.0)
        self.assertEqual(linear_decay(3000, 200, 2000), 0.0)    # worse than worst
        mid = linear_decay(1100, 200, 2000)
        self.assertTrue(49.0 <= mid <= 51.0)

    def test_none_is_zero(self):
        self.assertEqual(linear_decay(None, 200, 2000), 0.0)


class TestSubScores(unittest.TestCase):
    def test_mrt_closer_is_better(self):
        self.assertGreater(mrt_score(prox(nearest_mrt_distance_m=250)),
                           mrt_score(prox(nearest_mrt_distance_m=1500)))

    def test_bus_more_density_is_better(self):
        self.assertGreater(bus_score(prox(bus_stops_within_400m=5)),
                           bus_score(prox(bus_stops_within_400m=0)))

    def test_school_more_is_better(self):
        self.assertGreater(school_score(prox(schools_within_1km=3, schools_within_2km=6)),
                           school_score(prox(schools_within_1km=0, schools_within_2km=0)))

    def test_scores_bounded_0_100(self):
        for fn in (mrt_score, bus_score, school_score):
            v = fn(prox())
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 100.0)


class TestCombined(unittest.TestCase):
    def test_combined_bounded(self):
        c = combined_score(prox())
        self.assertGreaterEqual(c, 0.0)
        self.assertLessEqual(c, 100.0)

    def test_weights_normalized(self):
        # Supplying only MRT weight => combined equals the MRT sub-score.
        p = prox()
        self.assertAlmostEqual(combined_score(p, {"mrt": 1.0}), mrt_score(p), places=2)

    def test_zero_weights_raise(self):
        with self.assertRaises(ValueError):
            combined_score(prox(), {"mrt": 0.0, "bus": 0.0, "school": 0.0})


class TestBlockAndEstate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=12)

    def test_block_accessibility_shape(self):
        bid = self.repo.blocks()[0].block_id
        a = block_accessibility(self.repo, bid)
        for key in ("mrt_score", "bus_score", "school_score", "combined_score", "raw"):
            self.assertIn(key, a)

    def test_block_unknown_none(self):
        self.assertIsNone(block_accessibility(self.repo, 999999))

    def test_estate_combined_is_mean_of_blocks(self):
        pa_id = 1
        block_ids = [b.block_id for b in self.repo.blocks()
                     if b.planning_area_id == pa_id]
        combos = [block_accessibility(self.repo, b)["combined_score"]
                  for b in block_ids]
        expected = round(sum(combos) / len(combos), 2)
        est = estate_accessibility(self.repo, pa_id)
        self.assertAlmostEqual(est["combined_score"], expected, places=2)
        self.assertEqual(est["block_count"], len(block_ids))

    def test_estate_unknown_none(self):
        self.assertIsNone(estate_accessibility(self.repo, 999999))


if __name__ == "__main__":
    unittest.main()
