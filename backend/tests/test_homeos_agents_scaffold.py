"""Boundary checks for HomeOS agent functions.

Verifies the expected callables exist now that agents are implemented.
"""
import unittest

from app.services import homeos_agents


class TestHomeOSAgentsScaffold(unittest.TestCase):
    def test_expected_agent_functions_exist(self):
        expected = [
            "market_analysis_agent",
            "location_graph_agent",
            "risk_value_agent",
            "viewing_questions_agent",
            "worth_viewing_score",
        ]

        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(homeos_agents, name)))


if __name__ == "__main__":
    unittest.main()
