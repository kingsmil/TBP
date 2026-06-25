"""Tests for Estimated BTO Resale Availability (app.data.bto_mop)."""
from __future__ import annotations

import datetime as dt
import unittest

from app.data import bto_mop as m


class ClassificationAndMop(unittest.TestCase):
    def test_normalise_classification(self):
        self.assertEqual(m.normalise_classification("Standard"), "STANDARD")
        self.assertEqual(m.normalise_classification("Plus"), "PLUS")
        self.assertEqual(m.normalise_classification("Prime"), "PRIME")
        self.assertEqual(m.normalise_classification("PLH"), "PLH")
        self.assertEqual(m.normalise_classification("Unclassified"), "UNCLASSIFIED")
        self.assertEqual(m.normalise_classification(""), "UNKNOWN")
        self.assertEqual(m.normalise_classification(None), "UNKNOWN")
        self.assertEqual(m.normalise_classification("something weird"), "UNKNOWN")

    def test_mop_years_mapping(self):
        self.assertEqual(m.mop_years("STANDARD"), 5)
        self.assertEqual(m.mop_years("UNCLASSIFIED"), 5)
        self.assertEqual(m.mop_years("UNKNOWN"), 5)
        self.assertEqual(m.mop_years("PLUS"), 10)
        self.assertEqual(m.mop_years("PRIME"), 10)
        self.assertEqual(m.mop_years("PLH"), 10)


class DateHelpers(unittest.TestCase):
    def test_parse_partial_date(self):
        self.assertEqual(m.parse_partial_date("2024"), (dt.date(2024, 1, 1), False))
        self.assertEqual(m.parse_partial_date("2024-06"), (dt.date(2024, 6, 1), True))
        self.assertEqual(m.parse_partial_date("2024-06-15"), (dt.date(2024, 6, 15), True))
        self.assertEqual(m.parse_partial_date(""), (None, False))
        self.assertEqual(m.parse_partial_date(None), (None, False))
        self.assertEqual(m.parse_partial_date("garbage"), (None, False))

    def test_add_years_and_months(self):
        self.assertEqual(m.add_years(dt.date(2024, 6, 1), 5), dt.date(2029, 6, 1))
        self.assertEqual(m.add_years(dt.date(2024, 2, 29), 1), dt.date(2025, 2, 28))
        self.assertEqual(m.add_months(dt.date(2024, 1, 1), 42), dt.date(2027, 7, 1))


class EstimateCalculation(unittest.TestCase):
    def test_standard_completion_plus_five(self):
        rec = m.make_record(project_name="X", town="TAMPINES",
                            classification_raw="Standard", source_type="MANUAL_SEED",
                            completion="2024-06")
        self.assertEqual(rec["mop_years"], 5)
        self.assertEqual(rec["estimated_resale_eligible_date"], dt.date(2029, 6, 1))

    def test_plus_prime_completion_plus_ten(self):
        plus = m.make_record(project_name="P", town="BEDOK", classification_raw="Plus",
                             source_type="MANUAL_SEED", completion="2028-06")
        self.assertEqual(plus["mop_years"], 10)
        self.assertEqual(plus["estimated_resale_eligible_date"], dt.date(2038, 6, 1))

    def test_key_collection_anchor_preferred(self):
        rec = m.make_record(project_name="X", town="T", classification_raw="Standard",
                            source_type="MANUAL_SEED", completion="2024",
                            key_collection="2025-03")
        # eligible should be anchored on key-collection (2025-03), not completion.
        self.assertEqual(rec["estimated_key_collection_date"], dt.date(2025, 3, 1))
        self.assertEqual(rec["estimated_resale_eligible_date"], dt.date(2030, 3, 1))

    def test_missing_completion_yields_none(self):
        rec = m.make_record(project_name="X", town="T", classification_raw="Standard",
                            source_type="MANUAL_SEED", completion=None)
        self.assertIsNone(rec["estimated_resale_eligible_date"])
        self.assertIsNone(rec["estimated_completion_date"])


class ConfidenceScoring(unittest.TestCase):
    def test_high_when_month_known_in_seed(self):
        c, _ = m.confidence_for("MANUAL_SEED", month_known=True)
        self.assertEqual(c, "HIGH")

    def test_medium_when_year_only_in_seed(self):
        c, _ = m.confidence_for("MANUAL_SEED", month_known=False)
        self.assertEqual(c, "MEDIUM")

    def test_low_when_launch_derived(self):
        c, _ = m.confidence_for("HDB_LAUNCH_PAGE", month_known=True)
        self.assertEqual(c, "LOW")

    def test_explicit_override_wins(self):
        c, _ = m.confidence_for("MANUAL_SEED", month_known=False, explicit="LOW")
        self.assertEqual(c, "LOW")


class LaunchDerived(unittest.TestCase):
    def test_estimate_from_launch_rows(self):
        rows = [{"estate_name": "Tampines", "classification": "Standard",
                 "flat_types": "4 ROOM", "project_names": "Sun Plaza",
                 "exercise_id": "202406", "launch_start_date": dt.date(2024, 6, 1)}]
        out = m.estimate_from_launch_rows(rows)
        self.assertEqual(len(out), 1)
        rec = out[0]
        self.assertEqual(rec["confidence"], "LOW")
        self.assertEqual(rec["project_name"], "Sun Plaza")
        # completion = launch + 42mo = 2027-12; +5y MOP -> 2032-12
        self.assertEqual(rec["estimated_completion_date"], dt.date(2027, 12, 1))
        self.assertEqual(rec["estimated_resale_eligible_date"], dt.date(2032, 12, 1))

    def test_launch_row_without_date_skipped(self):
        rows = [{"estate_name": "X", "classification": "Standard",
                 "launch_start_date": None}]
        self.assertEqual(m.estimate_from_launch_rows(rows), [])


class BuildMergeAndSort(unittest.TestCase):
    def test_seed_overrides_launch_and_sorted_by_soonest(self):
        seed = [m.make_record(project_name="A", town="BEDOK", classification_raw="Standard",
                              source_type="MANUAL_SEED", completion="2030-01")]
        launch = [
            # duplicate of seed (same project/town/class) -> must be dropped
            {"estate_name": "BEDOK", "classification": "Standard", "project_names": "A",
             "flat_types": "4 ROOM", "exercise_id": "202401",
             "launch_start_date": dt.date(2024, 1, 1)},
            # earlier eligibility -> should sort first
            {"estate_name": "ANG MO KIO", "classification": "Standard", "project_names": "B",
             "flat_types": "3 ROOM", "exercise_id": "201801",
             "launch_start_date": dt.date(2018, 1, 1)},
        ]
        recs = m.build_estimates(seed, launch)
        names = [r["project_name"] for r in recs]
        self.assertEqual(names.count("A"), 1)  # seed dedupes the launch dup
        # B (2018 launch) becomes eligible before A (2030 completion + 5y)
        self.assertEqual(recs[0]["project_name"], "B")
        elig = [r["estimated_resale_eligible_date"] for r in recs]
        self.assertEqual(elig, sorted(elig))


class SeedValidation(unittest.TestCase):
    def test_valid_seed_passes(self):
        data = {"projects": [{"project_name": "X", "town": "BEDOK",
                              "flat_classification": "Plus",
                              "estimated_completion_date": "2029-06",
                              "source_type": "MANUAL_SEED"}]}
        self.assertEqual(m.validate_seed(data), [])

    def test_invalid_seed_reports_problems(self):
        data = {"projects": [
            {"flat_classification": "Plus", "estimated_completion_date": "2029"},  # no name
            {"project_name": "Y", "source_type": "BOGUS"},                          # bad source + no date
            {"project_name": "Z", "estimated_completion_date": "not-a-date"},       # unparseable
        ]}
        problems = m.validate_seed(data)
        self.assertTrue(any("missing project_name" in p for p in problems))
        self.assertTrue(any("invalid source_type" in p for p in problems))
        self.assertTrue(any("unparseable" in p for p in problems))

    def test_projects_must_be_list(self):
        self.assertEqual(m.validate_seed({"projects": "nope"}),
                         ["seed: 'projects' must be a list"])

    def test_bundled_seed_file_is_valid(self):
        import json
        data = json.loads(m.SEED_PATH.read_text(encoding="utf-8"))
        self.assertEqual(m.validate_seed(data), [])


if __name__ == "__main__":
    unittest.main()
