"""Noisy prompt regression checks for HomeOS profile extraction.

These are deliberately phrased like real chat input: abbreviations, missing
punctuation, mixed priorities, and negations. The live LLM output is merged with
this deterministic fallback before search, so these checks protect the full
agent path.
"""
import unittest
import asyncio

from app.data.seed import build_seeded_repo
from app.homeos.pipeline import parse_homeos_profile, _search_phase


class TestHomeOSPromptEval(unittest.TestCase):
    def prefs(self, prompt: str) -> dict:
        return parse_homeos_profile(prompt)["preferences"]

    def test_shorthand_flat_type_and_town_abbreviation(self):
        prefs = self.prefs("pls find 4rm tpy max 650k near mrt thx")

        self.assertEqual(prefs["flat_type"], "4 ROOM")
        self.assertEqual(prefs["town"], "TOA PAYOH")
        self.assertEqual(prefs["max_price"], 650000.0)
        self.assertEqual(prefs["commute_priority"], "high")

    def test_negated_school_need_does_not_create_family_profile(self):
        avatar = parse_homeos_profile("not picky but queenstown 3-rm 700k, no need schools")

        self.assertEqual(avatar["buyer_type"], "single")
        self.assertEqual(avatar["preferences"]["flat_type"], "3 ROOM")
        self.assertEqual(avatar["preferences"]["town"], "QUEENSTOWN")
        self.assertEqual(avatar["preferences"]["school_priority"], "low")

    def test_directional_region_does_not_override_specific_town(self):
        prefs = self.prefs("east side, ideally tampines, 5room under 1m, kids need schools")

        self.assertEqual(prefs["town"], "TAMPINES")
        self.assertEqual(prefs["flat_type"], "5 ROOM")
        self.assertEqual(prefs["school_priority"], "high")

    def test_slash_separated_cbd_and_close_mrt(self):
        prefs = self.prefs("central/cbd 4 room below 800k, MRT must be close")

        self.assertEqual(prefs["town"], "CENTRAL AREA")
        self.assertEqual(prefs["flat_type"], "4 ROOM")
        self.assertEqual(prefs["max_price"], 800000.0)
        self.assertEqual(prefs["commute_priority"], "high")

    def test_couple_workplaces_and_no_car(self):
        prefs = self.prefs(
            "couple: i work raffles place, wife works at jurong east. "
            "5 room <=900k, no car, buses ok"
        )

        self.assertEqual(prefs["flat_type"], "5 ROOM")
        self.assertEqual(prefs["max_price"], 900000.0)
        self.assertIsNone(prefs["town"])
        self.assertIn("raffles place", [x.lower() for x in prefs["work_locations"]])
        self.assertIn("jurong east", [x.lower() for x in prefs["partner_work_locations"]])
        self.assertEqual(prefs["bus_reliance"], "high")

    def test_workplace_town_does_not_become_preferred_town(self):
        prefs = self.prefs("I work in Tampines but prefer Bedok, 4 room under 700k")

        self.assertEqual(prefs["town"], "BEDOK")

    def test_multiple_preferred_towns_are_preserved(self):
        prefs = self.prefs("bedok or tampines is ok, 4 room max 700k")

        self.assertEqual(prefs["town"], "BEDOK")
        self.assertEqual(prefs["preferred_towns"], ["BEDOK", "TAMPINES"])

    def test_dont_drive_without_apostrophe_counts_as_bus_reliance(self):
        prefs = self.prefs("single, office in one-north, 2 room about 450k, dont drive")

        self.assertEqual(prefs["flat_type"], "2 ROOM")
        self.assertEqual(prefs["max_price"], 450000.0)
        self.assertEqual(prefs["work_locations"], ["one-north"])
        self.assertEqual(prefs["bus_reliance"], "high")

    def test_word_budget_and_loose_budget_phrasing(self):
        self.assertEqual(self.prefs("budget eight hundred k, 4-room")["max_price"], 800000.0)
        self.assertEqual(self.prefs("need 4 room, around 700-ish")["max_price"], 700000.0)
        self.assertEqual(self.prefs("cheap 3rm can stretch to 550")["max_price"], 550000.0)

    def test_negative_town_and_school_phrasing(self):
        prefs = self.prefs("no jurong please, prefer east, 3 room 500k")

        self.assertIsNone(prefs["town"])
        self.assertEqual(prefs["preferred_towns"], [])
        self.assertEqual(self.prefs("executive flat, not near schools, under $950,000")["school_priority"], "low")

    def test_shorthand_couple_work_locations_do_not_become_town(self):
        prefs = self.prefs("couple, me at one-north wife at cbd, 4rm 850k, dont drive")

        self.assertIsNone(prefs["town"])
        self.assertIn("one-north", [x.lower() for x in prefs["work_locations"]])
        self.assertIn("cbd", [x.lower() for x in prefs["partner_work_locations"]])
        self.assertEqual(prefs["bus_reliance"], "high")

    def test_overlapping_town_names_do_not_add_bukit_batok(self):
        prefs = self.prefs("parents elderly, lift access, near bus, queenstown or bukit merah")

        self.assertEqual(prefs["preferred_towns"], ["QUEENSTOWN", "BUKIT MERAH"])
        self.assertEqual(prefs["bus_reliance"], "high")

    def test_hdb_bedder_maps_to_room_type(self):
        prefs = self.prefs("2 bedder resale hdb under 450k in amk")

        self.assertEqual(prefs["flat_type"], "2 ROOM")
        self.assertEqual(prefs["town"], "ANG MO KIO")


class TestHomeOSSearchEval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=12)

    def test_search_runs_across_multiple_preferred_towns(self):
        prefs = parse_homeos_profile("bedok or tampines is ok, 4 room max 900k")["preferences"]

        async def run():
            return await _search_phase(self.repo, "case-multi-town", prefs)

        candidates, _, query = asyncio.run(run())

        self.assertEqual(query["preferred_towns"], ["BEDOK", "TAMPINES"])
        self.assertGreater(len(candidates), 0)
        self.assertTrue({c["town"] for c in candidates}.issubset({"BEDOK", "TAMPINES"}))

    def test_zero_result_search_relaxes_filters_with_trace(self):
        prefs = parse_homeos_profile("4 room under 1k")["preferences"]

        async def run():
            return await _search_phase(self.repo, "case-relax", prefs)

        candidates, _, query = asyncio.run(run())

        self.assertGreater(len(candidates), 0)
        self.assertIn("relaxation_applied", query)
        self.assertIn("strict_query", query)
        self.assertEqual(query["strict_query"]["max_price"], 1000.0)


if __name__ == "__main__":
    unittest.main()
