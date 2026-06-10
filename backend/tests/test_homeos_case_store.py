import unittest

from app.homeos.case_store import (
    append_event,
    append_message,
    create_case,
    get_case,
    list_cases,
)


class TestHomeOSCaseStore(unittest.TestCase):
    def setUp(self):
        from app.homeos import case_store
        case_store._cases.clear()

    def test_create_case_returns_case_with_id(self):
        case = create_case("Family looking for 4 room under 800k.")
        self.assertIsNotNone(case["case_id"])
        self.assertEqual(case["profile_text"], "Family looking for 4 room under 800k.")
        self.assertEqual(case["status"], "running")
        self.assertEqual(case["pipeline"], [])
        self.assertEqual(case["shortlist"], [])
        self.assertEqual(case["conversation"], [])

    def test_get_case_returns_same_case(self):
        case = create_case("test profile")
        fetched = get_case(case["case_id"])
        self.assertEqual(fetched["case_id"], case["case_id"])

    def test_get_case_returns_none_for_unknown_id(self):
        self.assertIsNone(get_case("nonexistent-id"))

    def test_list_cases_returns_newest_first(self):
        c1 = create_case("first")
        c2 = create_case("second")
        cases = list_cases()
        self.assertEqual(cases[0]["case_id"], c2["case_id"])
        self.assertEqual(cases[1]["case_id"], c1["case_id"])

    def test_append_event_adds_to_pipeline(self):
        case = create_case("test profile")
        event = {"event": "agent_start", "agent": "market", "block_id": 1}
        append_event(case["case_id"], event)
        updated = get_case(case["case_id"])
        self.assertEqual(len(updated["pipeline"]), 1)
        self.assertEqual(updated["pipeline"][0]["agent"], "market")

    def test_append_message_adds_to_conversation(self):
        case = create_case("test profile")
        append_message(case["case_id"], "user", "Why Bishan?")
        append_message(case["case_id"], "assistant", "Because of the schools.")
        updated = get_case(case["case_id"])
        self.assertEqual(len(updated["conversation"]), 2)
        self.assertEqual(updated["conversation"][0]["role"], "user")
        self.assertEqual(updated["conversation"][1]["content"], "Because of the schools.")


if __name__ == "__main__":
    unittest.main()
