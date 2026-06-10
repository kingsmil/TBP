"""Tests for seeding active listings from the bundled CSV snapshot."""
import csv
import tempfile
import unittest
from pathlib import Path

from tests.test_active_listings import make_block

SAMPLE_ROW = {
    "listing_id": "36066", "block_number": "56", "street_name": "LOR 4 TOA PAYOH",
    "postal_code": "310056", "town": "Toa Payoh", "price": "300000.00",
    "flat_type": "2-Room", "floor_area_sqm": "43.00", "storey_range": "6 to 10",
    "remaining_lease": "40 years ", "bedroom": "1", "bathroom": "1",
    "description": "Fully Renovated Unit.", "photo_path": "rf/36066/x.jpg",
    "agent_name": "JOHN DOE", "agent_phone": "91234567",
    "agent_email": "john.doe@example.com", "agency_name": "TBP PTE LTD",
    "managed_by_agent": "t", "last_updated": "2026-03-03 15:45:56.5",
}


def _write_csv(rows):
    tmp = tempfile.NamedTemporaryFile(
        "w", newline="", suffix=".csv", delete=False, encoding="utf-8")
    writer = csv.DictWriter(tmp, fieldnames=list(SAMPLE_ROW))
    writer.writeheader()
    writer.writerows(rows)
    tmp.close()
    return Path(tmp.name)


class RowToFieldsTest(unittest.TestCase):
    def test_types_and_psql_booleans(self):
        from app.data.seed_listings import row_to_fields
        fields = row_to_fields(dict(SAMPLE_ROW))
        self.assertEqual(fields["listing_id"], 36066)
        self.assertEqual(fields["price"], 300000.0)
        self.assertEqual(fields["bedroom"], 1)
        self.assertTrue(fields["managed_by_agent"])

    def test_empty_optionals_become_none(self):
        from app.data.seed_listings import row_to_fields
        row = dict(SAMPLE_ROW, bedroom="", bathroom="", description="",
                   agent_name="", agent_phone="", agent_email="",
                   agency_name="", photo_path="", managed_by_agent="f")
        fields = row_to_fields(row)
        self.assertIsNone(fields["bedroom"])
        self.assertIsNone(fields["agent_phone"])
        self.assertFalse(fields["managed_by_agent"])


class SeedListingsTest(unittest.TestCase):
    def test_rematches_blocks_and_skips_unknown(self):
        from app.data.seed_listings import seed_listings
        from app.repositories.memory import InMemoryRepository
        repo = InMemoryRepository()
        repo.add_blocks([make_block(block_id=7, number="56",
                                    street="LOR 4 TOA PAYOH", postal="")])
        path = _write_csv([
            SAMPLE_ROW,
            dict(SAMPLE_ROW, listing_id="999", block_number="999Z",
                 street_name="NOWHERE ST", postal_code=""),
        ])
        try:
            seeded, unmatched = seed_listings(repo, path)
        finally:
            path.unlink()
        self.assertEqual((seeded, unmatched), (1, 1))
        stored = repo.active_listings_for_block(7)
        self.assertEqual(stored[0].listing_id, 36066)
        self.assertEqual(stored[0].agent_phone, "91234567")

    def test_bundled_snapshot_exists_and_parses(self):
        from app.data.seed_listings import SNAPSHOT, row_to_fields
        self.assertTrue(SNAPSHOT.exists())
        with SNAPSHOT.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            first = row_to_fields(next(reader))
        self.assertGreater(first["price"], 0)


if __name__ == "__main__":
    unittest.main()
