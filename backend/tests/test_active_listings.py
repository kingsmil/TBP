"""Tests for ActiveListing model, repo methods, and listing→block matching."""
import unittest

from app.core.models import ActiveListing


def make_listing(**kw):
    base = dict(
        listing_id=40661, block_id=1, block_number="126A",
        street_name="KIM TIAN RD", postal_code="161126", town="Bukit Merah",
        price=1330000.0, flat_type="4-Room", floor_area_sqm=93.0,
        storey_range="More than 30", remaining_lease="85 years 8 months",
        bedroom=3, bathroom=2, description="Rare top-floor gem",
        photo_path="rf/40661/40661-IMG.jpg", agent_name=None, agent_phone=None,
        agent_email=None, agency_name=None, managed_by_agent=False,
        last_updated="2026-06-10 01:07:50",
    )
    base.update(kw)
    return ActiveListing(**base)


class ActiveListingModelTest(unittest.TestCase):
    def test_floor_area_sqft_derived(self):
        listing = make_listing()
        self.assertAlmostEqual(listing.floor_area_sqft, 93.0 * 10.7639, places=2)

    def test_nullable_agent_fields_default_none(self):
        listing = make_listing()
        self.assertIsNone(listing.agent_name)
        self.assertFalse(listing.managed_by_agent)


class ActiveListingRepoTest(unittest.TestCase):
    def test_add_and_read_listings_by_block(self):
        from app.repositories.memory import InMemoryRepository
        repo = InMemoryRepository()
        repo.add_active_listings([
            make_listing(listing_id=1, block_id=10),
            make_listing(listing_id=2, block_id=10, price=900000.0),
            make_listing(listing_id=3, block_id=11),
        ])
        ten = repo.active_listings_for_block(10)
        self.assertEqual({l.listing_id for l in ten}, {1, 2})
        self.assertEqual(list(repo.active_listings_for_block(99)), [])
        self.assertEqual(repo.active_listing(3).block_id, 11)
        self.assertIsNone(repo.active_listing(99))

    def test_upsert_replaces_same_listing_id(self):
        from app.repositories.memory import InMemoryRepository
        repo = InMemoryRepository()
        repo.add_active_listings([make_listing(listing_id=1, block_id=10, price=1.0)])
        repo.add_active_listings([make_listing(listing_id=1, block_id=10, price=2.0)])
        self.assertEqual(len(repo.active_listings_for_block(10)), 1)
        self.assertEqual(repo.active_listing(1).price, 2.0)


if __name__ == "__main__":
    unittest.main()
