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

    def test_resale_and_rent_can_share_listing_id(self):
        from app.repositories.memory import InMemoryRepository
        repo = InMemoryRepository()
        repo.add_active_listings([
            make_listing(listing_id=1, block_id=10, price=900000.0),
            make_listing(listing_type="rent", listing_id=1, block_id=10, price=3600.0),
        ])
        self.assertEqual(len(repo.active_listings_for_block(10)), 2)
        self.assertEqual(len(repo.active_listings_for_block(10, "resale")), 1)
        self.assertEqual(len(repo.active_listings_for_block(10, "rent")), 1)
        self.assertEqual(repo.active_listing(1, "rent").price, 3600.0)
        self.assertIsNone(repo.active_listing(1))


def make_block(block_id=1, number="126A", street="KIM TIAN RD", postal="161126"):
    from app.core.geo import Point
    from app.core.models import Block
    return Block(block_id=block_id, block_number=number, street_name=street,
                 postal_code=postal, town="BUKIT MERAH", planning_area_id=None,
                 lease_commencement_year=2001, point=Point(103.83, 1.28))


class StreetNormTest(unittest.TestCase):
    def test_abbreviations_collapse(self):
        from app.data.hdb_listings import normalize_street
        self.assertEqual(normalize_street("Kim Tian Road"), "KIM TIAN RD")
        self.assertEqual(normalize_street("ANG MO KIO AVENUE 3"), "ANG MO KIO AVE 3")
        self.assertEqual(normalize_street("  jurong   west st 42 "), "JURONG WEST ST 42")


class BlockMatcherTest(unittest.TestCase):
    def test_tier1_postal_exact(self):
        from app.data.hdb_listings import BlockMatcher
        m = BlockMatcher([make_block()])
        bid, tier = m.match(postal="161126", block="999Z", street="NOWHERE")
        self.assertEqual((bid, tier), (1, 1))

    def test_tier2_block_street_when_postal_missing_on_our_side(self):
        from app.data.hdb_listings import BlockMatcher
        m = BlockMatcher([make_block(postal="")])
        bid, tier = m.match(postal="161126", block="126a", street="Kim Tian Road")
        self.assertEqual((bid, tier), (1, 2))

    def test_no_match_returns_none(self):
        from app.data.hdb_listings import BlockMatcher
        m = BlockMatcher([make_block()])
        bid, tier = m.match(postal="999999", block="1", street="FAKE ST")
        self.assertEqual((bid, tier), (None, 0))


def _load_fixture():
    import json
    import pathlib
    path = pathlib.Path(__file__).parent / "fixtures" / "hdb_detail_40661.json"
    return json.loads(path.read_text())


class ParseDetailTest(unittest.TestCase):
    def test_parse_recorded_fixture(self):
        from app.data.hdb_listings import parse_detail
        d = parse_detail(_load_fixture(), 40661)
        self.assertEqual(d["postal_code"], "161126")
        self.assertEqual(d["price"], 1330000)
        self.assertEqual(d["listing_type"], "resale")
        self.assertEqual(d["block_number"], "126A")
        self.assertEqual(d["street_name"], "KIM TIAN RD")
        self.assertEqual(d["flat_type"], "4-Room")
        self.assertEqual(d["floor_area_sqm"], 93.0)
        self.assertIn("Top-Floor Gem", d["description"])
        # Agent contact is not public on the portal (spec §3.3).
        self.assertIsNone(d["agent_name"])
        self.assertFalse(d["managed_by_agent"])


class IngestTest(unittest.TestCase):
    def test_ingest_matches_and_stores(self):
        from app.data.hdb_listings import ingest_listings
        from app.repositories.memory import InMemoryRepository
        repo = InMemoryRepository()
        repo.add_blocks([make_block()])
        raw = _load_fixture()
        report = ingest_listings(
            repo,
            fetch_markers=lambda: ["40661"],
            fetch_detail=lambda lid: raw,
        )
        self.assertEqual(report.listings_fetched, 1)
        self.assertEqual(report.matched_tier1, 1)
        self.assertEqual(report.unmatched, 0)
        stored = repo.active_listings_for_block(1)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].listing_id, 40661)
        self.assertEqual(stored[0].price, 1330000.0)
        self.assertEqual(stored[0].listing_type, "resale")

    def test_unmatched_listing_is_skipped_and_counted(self):
        from app.data.hdb_listings import ingest_listings
        from app.repositories.memory import InMemoryRepository
        repo = InMemoryRepository()  # no blocks at all
        report = ingest_listings(
            repo,
            fetch_markers=lambda: ["40661"],
            fetch_detail=lambda lid: _load_fixture(),
        )
        self.assertEqual(report.unmatched, 1)
        self.assertEqual(report.matched_tier1 + report.matched_tier2, 0)

    def test_failed_detail_fetch_does_not_abort_batch(self):
        from app.data.hdb_listings import ingest_listings
        from app.repositories.memory import InMemoryRepository
        repo = InMemoryRepository()
        repo.add_blocks([make_block()])

        def flaky(lid):
            if lid == "111":
                raise RuntimeError("boom")
            return _load_fixture()

        report = ingest_listings(
            repo, fetch_markers=lambda: ["111", "40661"], fetch_detail=flaky)
        self.assertEqual(report.fetch_errors, 1)
        self.assertEqual(report.matched_tier1, 1)


class BlockListingsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.api.main import app
        from app.repositories.memory import InMemoryRepository

        repo = InMemoryRepository()
        repo.add_blocks([make_block()])
        repo.add_active_listings([
            make_listing(listing_id=2, block_id=1, price=1330000.0),
            make_listing(listing_id=1, block_id=1, price=900000.0),
            make_listing(
                listing_type="rent", listing_id=1, block_id=1, price=3600.0,
                remaining_lease="",
            ),
        ])
        cls._override = repo
        app.dependency_overrides[deps.get_repository] = lambda: repo
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from app.api import deps
        from app.api.main import app
        app.dependency_overrides.pop(deps.get_repository, None)

    def test_listings_sorted_by_price_with_sqft(self):
        res = self.client.get("/blocks/1/listings")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["count"], 2)
        self.assertTrue(all(l["listing_type"] == "resale" for l in body["listings"]))
        prices = [l["price"] for l in body["listings"]]
        self.assertEqual(prices, sorted(prices))
        self.assertAlmostEqual(
            body["listings"][0]["floor_area_sqft"], round(93.0 * 10.7639, 1))

    def test_null_agent_fields_omitted(self):
        res = self.client.get("/blocks/1/listings")
        first = res.json()["listings"][0]
        self.assertNotIn("agent_name", first)
        self.assertNotIn("agent_phone", first)

    def test_unknown_block_404(self):
        self.assertEqual(self.client.get("/blocks/999/listings").status_code, 404)

    def test_rent_query_returns_rental_listings(self):
        res = self.client.get("/blocks/1/listings?listing_type=rent")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["listings"][0]["listing_type"], "rent")
        self.assertEqual(body["listings"][0]["price"], 3600.0)

    def test_all_query_returns_resale_and_rent(self):
        res = self.client.get("/blocks/1/listings?listing_type=all")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 3)

    def test_bad_listing_type_422(self):
        res = self.client.get("/blocks/1/listings?listing_type=lease")
        self.assertEqual(res.status_code, 422)

    def test_block_without_listings_empty_list(self):
        self._override.add_blocks([make_block(block_id=2, postal="161127")])
        res = self.client.get("/blocks/2/listings")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["listings"], [])


if __name__ == "__main__":
    unittest.main()
