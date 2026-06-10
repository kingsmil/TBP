import unittest

from app.homeos.sync_agents import base_viewing_questions


class TestBaseViewingQuestions(unittest.TestCase):
    def test_returns_base_questions_without_llm(self):
        qs = base_viewing_questions({"market": {}, "location": {}, "risk": {}})
        self.assertIn("Which floor range is the unit in?", qs)
        self.assertTrue(all(isinstance(q, str) for q in qs))

    def test_low_market_confidence_adds_question(self):
        qs = base_viewing_questions({"market": {"confidence": "low"}, "location": {}})
        self.assertTrue(any("limited recent resale evidence" in q for q in qs))

    def test_weak_connection_adds_question(self):
        qs = base_viewing_questions(
            {"market": {}, "location": {"connections": [{"signal": "weak"}]}}
        )
        self.assertTrue(any("realistic walking route" in q for q in qs))


if __name__ == "__main__":
    unittest.main()
