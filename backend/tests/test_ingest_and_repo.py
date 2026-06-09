"""Tests for mock-data generation, ingestion, and the in-memory repository."""
import unittest

from app.data.ingest import compute_proximity, ingest
from app.data.mock import generate
from app.repositories.memory import InMemoryRepository


class TestMockGeneration(unittest.TestCase):
    def test_deterministic(self):
        a = generate(seed=7, blocks_per_area=4, months=6)
        b = generate(seed=7, blocks_per_area=4, months=6)
        self.assertEqual(len(a.blocks), len(b.blocks))
        self.assertEqual(a.blocks[0], b.blocks[0])
        self.assertEqual(a.transactions[0], b.transactions[0])

    def test_counts_scale_with_params(self):
        d = generate(seed=1, blocks_per_area=5, months=12, txns_per_block_month=1)
        # 5 areas * 5 blocks.
        self.assertEqual(len(d.blocks), 25)
        # Each block has 12 monthly transactions.
        self.assertEqual(len(d.transactions), 25 * 12)


class TestIngestion(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryRepository()
        self.dataset = generate(seed=42, blocks_per_area=6, months=12)
        self.report = ingest(self.dataset, self.repo)

    def test_blocks_loaded(self):
        self.assertEqual(self.report.blocks_loaded, len(self.repo.blocks()))
        self.assertGreater(self.report.blocks_loaded, 0)

    def test_planning_area_fk_resolved(self):
        # Every mock block sits inside its generating rectangle, so PIP must
        # resolve a planning area for all of them.
        self.assertEqual(self.report.blocks_with_planning_area,
                         self.report.blocks_loaded)
        for b in self.repo.blocks():
            self.assertIsNotNone(b.planning_area_id)

    def test_proximity_complete(self):
        self.assertEqual(self.report.proximity_rows, self.report.blocks_loaded)
        for b in self.repo.blocks():
            prox = self.repo.proximity(b.block_id)
            self.assertIsNotNone(prox)
            self.assertIsNotNone(prox.nearest_mrt_station_id)
            self.assertGreaterEqual(prox.nearest_mrt_distance_m, 0)

    def test_future_mrt_distinct_from_operational(self):
        b = self.repo.blocks()[0]
        prox = self.repo.proximity(b.block_id)
        self.assertIsNotNone(prox.nearest_future_mrt_station_id)
        ops_ids = {m.station_id for m in self.repo.mrt_stations("operational")}
        self.assertIn(prox.nearest_mrt_station_id, ops_ids)

    def test_transactions_only_for_loaded_blocks(self):
        loaded = {b.block_id for b in self.repo.blocks()}
        for t in self.repo.transactions():
            self.assertIn(t.block_id, loaded)

    def test_rejects_out_of_bounds_block(self):
        # Move one block far outside Singapore; it must be rejected.
        from dataclasses import replace
        from app.core.geo import Point
        bad = replace(self.dataset.blocks[0], block_id=99999,
                      point=Point(0.0, 0.0))
        ds = self.dataset
        ds.blocks.append(bad)
        repo2 = InMemoryRepository()
        rep2 = ingest(ds, repo2)
        self.assertGreaterEqual(rep2.blocks_rejected, 1)
        self.assertIsNone(repo2.block(99999))


class TestTransactionDerivedFields(unittest.TestCase):
    def test_psf_and_sqft(self):
        d = generate(seed=3, blocks_per_area=2, months=2)
        t = d.transactions[0]
        self.assertAlmostEqual(t.floor_area_sqft, t.floor_area_sqm * 10.7639, places=4)
        self.assertAlmostEqual(t.psf, t.resale_price / t.floor_area_sqft, places=6)


if __name__ == "__main__":
    unittest.main()
