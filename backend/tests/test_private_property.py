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

    def test_stable_id(self):
        t = {"area": "100", "contractDate": "0324", "price": "2000000",
             "typeOfSale": "1", "propertyType": "Condominium"}
        a = normalise.normalise_transaction("X", None, None, None, None, t)
        b = normalise.normalise_transaction("X", None, None, None, None, dict(t))
        self.assertEqual(a["id"], b["id"])


class ServiceFilters(unittest.TestCase):
    def setUp(self):
        ura_client.refresh()  # ensure fixtures loaded
        self.assertTrue(ura_client.is_mock())

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

    def test_empty_state_for_unknown_project(self):
        data = service.transactions(project="zzz-nonexistent")
        self.assertEqual(data["summary"]["count"], 0)
        self.assertEqual(data["results"], [])
        self.assertIsNone(data["latest"])

    def test_projects_listing(self):
        p = service.projects()
        self.assertGreaterEqual(p["count"], 1)
        self.assertIn("THE CONTINUUM", [x["project_name"] for x in p["results"]])


if __name__ == "__main__":
    unittest.main()
