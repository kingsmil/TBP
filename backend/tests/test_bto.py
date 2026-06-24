"""Tests for BTO application-rate parsing."""
from __future__ import annotations

import unittest

from app.data.bto import parse_exercise, _label

_RAW = {
    "is_final_update": False,
    "launch_start_date": "2026-06-17",
    "launch_end_date": "2026-06-24",
    "estate_list": [
        {
            "estate_name": "Ang Mo Kio",
            "flat_type_list": [
                {
                    "flat_type": "2-Room Flexi",
                    "projects": [{"project_name": "Kebun Baru Breeze", "project_classification": "Plus"}],
                    "flat_supply": 377, "total_applicant_no": 925,
                    "app_rates": {"elderly": 2.4, "first_time_fam": 0.1,
                                  "second_time_fam": 0.3, "first_time_singles": 3.7},
                },
                {
                    "flat_type": "4-Room",
                    "projects": [
                        {"project_name": "Kebun Baru Breeze", "project_classification": "Plus"},
                        {"project_name": "Kebun Baru Ridge", "project_classification": "Plus"},
                    ],
                    "flat_supply": 592, "total_applicant_no": 1122,
                    "app_rates": {"elderly": None, "first_time_fam": 1.3,
                                  "second_time_fam": 7.2, "first_time_singles": None},
                },
            ],
        },
    ],
}


class TestBtoParse(unittest.TestCase):
    def test_label(self):
        self.assertEqual(_label("202606"), "June 2026")
        self.assertEqual(_label("202602"), "February 2026")

    def test_summary_totals(self):
        summary, rows = parse_exercise("202606", _RAW)
        self.assertEqual(summary["exercise_id"], "202606")
        self.assertEqual(summary["label"], "June 2026")
        self.assertEqual(summary["estate_count"], 1)
        self.assertEqual(summary["total_units"], 377 + 592)
        self.assertEqual(summary["total_applicants"], 925 + 1122)
        self.assertAlmostEqual(summary["overall_app_rate"], round(2047 / 969, 2))

    def test_rows_shape(self):
        _, rows = parse_exercise("202606", _RAW)
        self.assertEqual(len(rows), 2)
        r0 = rows[0]
        self.assertEqual(r0["estate_name"], "Ang Mo Kio")
        self.assertEqual(r0["flat_type"], "2-Room Flexi")
        self.assertEqual(r0["classification"], "Plus")
        self.assertEqual(r0["overall_rate"], round(925 / 377, 2))
        self.assertEqual(r0["rate_first_time_fam"], 0.1)

    def test_multiple_projects_joined(self):
        _, rows = parse_exercise("202606", _RAW)
        self.assertEqual(rows[1]["project_names"], "Kebun Baru Breeze, Kebun Baru Ridge")

    def test_zero_supply_safe(self):
        raw = {"estate_list": [{"estate_name": "X", "flat_type_list": [
            {"flat_type": "4-Room", "projects": [], "flat_supply": 0,
             "total_applicant_no": 0, "app_rates": {}}]}]}
        summary, rows = parse_exercise("202610", raw)
        self.assertIsNone(rows[0]["overall_rate"])
        self.assertIsNone(summary["overall_app_rate"])


if __name__ == "__main__":
    unittest.main()
