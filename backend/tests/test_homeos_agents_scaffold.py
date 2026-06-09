"""Boundary checks for HomeOS agent functions."""
import unittest

from app.homeos import sync_agents
from app.homeos import scoring


class TestHomeOSAgentsScaffold(unittest.TestCase):
    def test_expected_sync_agent_functions_exist(self):
        expected = [
            "market_analysis_agent",
            "location_graph_agent",
            "risk_value_agent",
            "viewing_questions_agent",
        ]
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(sync_agents, name)))

    def test_scoring_functions_exist(self):
        for name in ("worth_viewing_score", "_verdict", "_confidence"):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(scoring, name)))


if __name__ == "__main__":
    unittest.main()
