"""Tests for Private Property mode (Feature 2): URA normalisation + filters.

Runs in mock mode (no URA creds) using bundled fixtures.
"""
from __future__ import annotations

import unittest

from app.services.private_property import normalise, service
from app.services.private_property import ura_client


class Normalisation(unittest.TestCase):
    def test_property_type_mapping(self):
        self.assertEqual(normalise.normalise_property_type("Condominium", "Strata"), "CONDO")
        self.assertEqual(normalise.normalise_property_type("Apartment", "Strata"), "APARTMENT")
        self.assertEqual(normalise.normalise_property_type("Executive Condominium", "Strata"), "EC")
        self.assertEqual(normalise.normalise_property_type("Terrace", "Land"), "LANDED")
        self.assertEqual(normalise.normalise_property_type("Terrace", "Strata"), "STRATA_LANDED")
        self.assertEqual(normalise.normalise_property_type("Strata Detached", "Strata"), "STRATA_LANDED")

    def test_sale_type_and_date(self):
        self.assertEqual(normalise.parse_contract_date("0124"), "2024-01-01")
        self.assertEqual(normalise.parse_contract_date("1223"), "2023-12-01")
        self.assertIsNone(normalise.parse_contract_date("1324"))  # bad month
        self.assertIsNone(normalise.parse_contract_date(""))
        self.assertIsNone(normalise.parse_contract_date(None))

    def test_normalise_transaction_psf_and_fields(self):
        t = {"area": "100", "floorRange": "06-10", "contractDate": "0324",
             "typeOfSale": "3", "price": "2000000", "propertyType": "Condominium",
             "district": "15", "tenure": "Freehold", "typeOfArea": "Strata"}
        row = normalise.normalise_transaction("X", "Y ST", "RCR", None, None, t)
        self.assertEqual(row["sale_type"], "RESALE")
        self.assertEqual(row["property_type"], "CONDO")
        self.assertEqual(row["sale_date"], "2024-03-01")
        self.assertEqual(row["area_sqft"], round(100 * 10.7639, 1))
        # psf = 2_000_000 / 1076.39 ~ 1858
        self.assertAlmostEqual(row["psf"], round(2000000 / (100 * 10.7639)), delta=1)
        self.assertEqual(row["source"], "URA")

    def test_unusable_rows_dropped(self):
        # No price -> dropped.
        self.assertIsNone(normalise.normalise_transaction("X", None, None, None, None,
            {"area": "100", "contractDate": "0324", "price": "0"}))
        # No date -> dropped.
        self.assertIsNone(normalise.normalise_transaction("X", None, None, None, None,
            {"area": "100", "contractDate": "", "price": "100"}))

    def test_batch_ids_unique_even_for_identical_caveats(self):
        # Two indistinguishable caveats (same project/date/price/area/floor/units)
        # must still get distinct ids (PK + UI key safety).
        proj = {"project": "X", "transaction": [
            {"area": "100", "contractDate": "0324", "price": "2000000",
             "typeOfSale": "1", "propertyType": "Condominium", "floorRange": "06-10", "noOfUnits": "1"},
            {"area": "100", "contractDate": "0324", "price": "2000000",
             "typeOfSale": "1", "propertyType": "Condominium", "floorRange": "06-10", "noOfUnits": "1"},
        ]}
        rows = normalise.normalise_batch([proj])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r["id"] for r in rows}), 2)

    def test_stable_id(self):
        t = {"area": "100", "contractDate": "0324", "price": "2000000",
             "typeOfSale": "1", "propertyType": "Condominium"}
        a = normalise.normalise_transaction("X", None, None, None, None, t)
        b = normalise.normalise_transaction("X", None, None, None, None, dict(t))
        self.assertEqual(a["id"], b["id"])


class ServiceFilters(unittest.TestCase):
    def setUp(self):
        # Pin mock mode so the suite is deterministic + offline even when a real
        # URA_ACCESS_KEY is configured in the environment.
        self._is_mock = ura_client.is_mock
        self._db_engine = service._db_engine
        ura_client.is_mock = lambda: True
        service._db_engine = lambda: None  # exercise the in-memory fixture path
        ura_client.refresh()  # reload fixtures under mock mode
        self.assertTrue(ura_client.is_mock())

    def tearDown(self):
        ura_client.is_mock = self._is_mock
        service._db_engine = self._db_engine
        ura_client._cache.invalidate()  # drop fixtures; reload lazily, no network here

    def test_summary_and_trend(self):
        data = service.transactions()
        self.assertGreater(data["summary"]["count"], 0)
        self.assertIsNotNone(data["summary"]["median_psf"])
        self.assertLessEqual(data["summary"]["min_psf"], data["summary"]["max_psf"])
        self.assertTrue(data["mock"])
        self.assertTrue(all(a["month"] <= b["month"]
                            for a, b in zip(data["trend"], data["trend"][1:])))

    def test_filter_by_property_type(self):
        ec = service.transactions(property_type="EC")
        self.assertTrue(all(r["property_type"] == "EC" for r in ec["results"]))
        self.assertGreaterEqual(ec["summary"]["count"], 1)

    def test_filter_by_sale_type_and_project(self):
        sub = service.transactions(sale_type="SUB_SALE")
        self.assertTrue(all(r["sale_type"] == "SUB_SALE" for r in sub["results"]))
        cont = service.transactions(project="continuum")
        self.assertTrue(all("CONTINUUM" in (r["project_name"] or "").upper() for r in cont["results"]))

    def test_filter_by_date_range(self):
        data = service.transactions(date_from="2024-05-01", date_to="2024-12-31")
        self.assertTrue(all("2024-05-01" <= r["sale_date"] <= "2024-12-31" for r in data["results"]))

    def test_filter_by_location_tenure_and_floor(self):
        data = service.transactions(
            district="15",
            planning_region="RCR",
            tenure="freehold",
            floor_range="06-10",
        )
        self.assertGreaterEqual(data["summary"]["count"], 1)
        self.assertTrue(all((r["district"] or "").zfill(2) == "15" for r in data["results"]))
        self.assertTrue(all(r["planning_region"] == "RCR" for r in data["results"]))
        self.assertTrue(all("Freehold" in (r["tenure"] or "") for r in data["results"]))
        self.assertTrue(all(r["floor_range"] == "06-10" for r in data["results"]))

    def test_filter_by_numeric_ranges_and_address(self):
        data = service.transactions(
            address="jalan",
            min_price=1_400_000,
            max_price=1_700_000,
            min_psf=1_750,
            max_area_sqft=950,
        )
        self.assertGreaterEqual(data["summary"]["count"], 1)
        self.assertTrue(all("JALAN" in (r["address"] or "").upper() for r in data["results"]))
        self.assertTrue(all(1_400_000 <= r["price"] <= 1_700_000 for r in data["results"]))
        self.assertTrue(all(r["psf"] is not None and r["psf"] >= 1_750 for r in data["results"]))
        self.assertTrue(all(r["area_sqft"] is not None and r["area_sqft"] <= 950 for r in data["results"]))

    def test_filter_metadata_includes_private_facets(self):
        data = service.transactions(limit=1)
        self.assertIn("planning_regions", data["filters"])
        self.assertIn("tenures", data["filters"])
        self.assertIn("floor_ranges", data["filters"])

    def test_empty_state_for_unknown_project(self):
        data = service.transactions(project="zzz-nonexistent")
        self.assertEqual(data["summary"]["count"], 0)
        self.assertEqual(data["results"], [])
        self.assertIsNone(data["latest"])

    def test_projects_listing(self):
        p = service.projects()
        self.assertGreaterEqual(p["count"], 1)
        self.assertIn("THE CONTINUUM", [x["project_name"] for x in p["results"]])


class TokenRenewal(unittest.TestCase):
    """Auto-renewal: cache a valid token, reuse it, renew when expired/forced."""

    def setUp(self):
        self._mint = ura_client._mint_token
        self._tok = dict(ura_client._token)
        self.calls = 0

        def fake_mint():
            self.calls += 1
            return f"token-{self.calls}"

        ura_client._mint_token = fake_mint
        ura_client._token = {"value": None, "expires": 0.0}

    def tearDown(self):
        ura_client._mint_token = self._mint
        ura_client._token = self._tok

    def test_reuses_until_expiry_then_renews(self):
        t1 = ura_client.current_token()
        t2 = ura_client.current_token()
        self.assertEqual(t1, t2)
        self.assertEqual(self.calls, 1)  # cached, not re-minted

        # Forced renewal (e.g. after a 401) mints a fresh token.
        t3 = ura_client.current_token(force=True)
        self.assertNotEqual(t3, t1)
        self.assertEqual(self.calls, 2)

        # Simulate expiry -> auto-renew on next call.
        ura_client._token["expires"] = 0.0
        t4 = ura_client.current_token()
        self.assertEqual(self.calls, 3)
        self.assertEqual(t4, "token-3")


if __name__ == "__main__":
    unittest.main()
