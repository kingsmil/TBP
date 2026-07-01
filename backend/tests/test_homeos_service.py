import asyncio
import unittest

from app.homeos import case_store as homeos_case_store
from app.homeos.pipeline import (
    _apply_rule_profile_fallback,
    _direct_answer_overrides,
    chat_in_case,
    parse_homeos_profile,
)


class TestHomeOSService(unittest.TestCase):
    def test_parse_family_profile(self):
        avatar = parse_homeos_profile(
            "We are a young family, budget 750k, need 4-room, care about primary schools, "
            "one parent works in Raffles Place, low risk tolerance."
        )

        self.assertEqual(avatar["label"], "Family HomeOS Agent")
        self.assertEqual(avatar["buyer_type"], "family")
        self.assertEqual(avatar["preferences"]["flat_type"], "4 ROOM")
        self.assertEqual(avatar["preferences"]["max_price"], 750000.0)
        self.assertEqual(avatar["preferences"]["school_priority"], "high")
        self.assertEqual(avatar["preferences"]["risk_tolerance"], "low")
        self.assertEqual(avatar["preferences"]["commute_priority"], "medium")

    def test_parse_commute_first_profile(self):
        avatar = parse_homeos_profile(
            "Single professional looking for executive flat below 1.1m, must be close to MRT, "
            "okay with some appreciation risk."
        )

        self.assertEqual(avatar["label"], "Commute HomeOS Agent")
        self.assertEqual(avatar["buyer_type"], "single")
        self.assertEqual(avatar["preferences"]["flat_type"], "EXECUTIVE")
        self.assertEqual(avatar["preferences"]["max_price"], 1100000.0)
        self.assertEqual(avatar["preferences"]["commute_priority"], "high")
        self.assertEqual(avatar["preferences"]["risk_tolerance"], "medium")

    def test_parse_town_and_three_room_profile(self):
        avatar = parse_homeos_profile("I want a 3 room in Serangoon under $700k.")

        self.assertEqual(avatar["preferences"]["flat_type"], "3 ROOM")
        self.assertEqual(avatar["preferences"]["town"], "SERANGOON")
        self.assertEqual(avatar["preferences"]["max_price"], 700000.0)

    def test_rule_fallback_fills_default_model_profile(self):
        avatar = {
            "label": "HomeOS Agent",
            "buyer_type": "single",
            "summary": "",
            "preferences": {
                "flat_type": None,
                "max_price": None,
                "town": None,
                "commute_priority": "low",
                "school_priority": "low",
                "risk_tolerance": "low",
                "appreciation_priority": "medium",
                "work_locations": [],
                "partner_work_locations": [],
                "bus_reliance": "low",
            },
        }

        merged = _apply_rule_profile_fallback(
            avatar,
            "I want a 3 room in Serangoon under 700k.",
        )

        self.assertEqual(merged["preferences"]["flat_type"], "3 ROOM")
        self.assertEqual(merged["preferences"]["town"], "SERANGOON")
        self.assertEqual(merged["preferences"]["max_price"], 700000.0)

    def test_direct_override_handles_terse_flat_type_change(self):
        pipeline = [{
            "event": "clarifying_question",
            "field": "ready_to_proceed",
            "question": "Ready to analyse 5 blocks? Tap Proceed to start, or keep refining.",
        }]

        overrides = _direct_answer_overrides("actually can add a 4 instead", pipeline)

        self.assertEqual(overrides["flat_type"], "4 ROOM")

    def test_direct_override_updates_town_and_flat_type_from_one_message(self):
        pipeline = [{
            "event": "clarifying_question",
            "field": "open_ended",
            "question": "Anything else you'd like? Or say proceed.",
        }]

        overrides = _direct_answer_overrides("make it 4 room in Serangoon", pipeline)

        self.assertEqual(overrides["flat_type"], "4 ROOM")
        self.assertEqual(overrides["town"], "SERANGOON")

    def test_direct_override_can_loosen_filters_after_no_results(self):
        pipeline = [{
            "event": "clarifying_question",
            "field": "no_results",
            "question": "I found 0 matching blocks with those filters.",
        }]

        overrides = _direct_answer_overrides("any town and no budget", pipeline)

        self.assertIsNone(overrides["town"])
        self.assertIsNone(overrides["max_price"])

    def test_chat_refuses_non_estate_questions(self):
        homeos_case_store._cases.clear()
        case = homeos_case_store.create_case("I want a 3 room in Serangoon under $700k.")
        homeos_case_store.set_status(case["case_id"], "done")

        async def run():
            chunks = []
            async for chunk in chat_in_case(case["case_id"], "Write me a pasta recipe"):
                chunks.append(chunk)
            return "".join(chunks)

        answer = asyncio.run(run())

        self.assertIn("Singapore property", answer)
        self.assertIn("only help", answer)


if __name__ == "__main__":
    unittest.main()
