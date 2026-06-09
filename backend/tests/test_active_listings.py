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


if __name__ == "__main__":
    unittest.main()
