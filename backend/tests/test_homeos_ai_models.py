import asyncio
import unittest

from app.services.homeos_ai_models import (
    AgentQuestions,
    HomeOSAvatar,
    HomeOSPreferences,
    LocationEvidence,
    MarketEvidence,
    RiskEvidence,
    WorthViewingResult,
)


class TestHomeOSAIModels(unittest.TestCase):
    def test_market_evidence_budget_signal_literals(self):
        m = MarketEvidence(
            transaction_count=6,
            median_price=710000.0,
            median_psf=650.0,
            budget_signal="within_budget",
            confidence="high",
            narrative="6 recent 4-room sales support the budget.",
        )
        self.assertEqual(m.budget_signal, "within_budget")
        self.assertEqual(m.confidence, "high")
        self.assertEqual(m.transaction_count, 6)

    def test_market_evidence_defaults(self):
        m = MarketEvidence()
        self.assertEqual(m.transaction_count, 0)
        self.assertIsNone(m.median_price)
        self.assertEqual(m.budget_signal, "unknown")
        self.assertEqual(m.confidence, "low")
        self.assertEqual(m.narrative, "")

    def test_location_evidence_connections(self):
        loc = LocationEvidence(
            connections=[
                {"type": "mrt", "name": "Nearest MRT", "distance_m": 620.0, "signal": "moderate"},
                {"type": "primary_school", "name": "Schools 1km", "count": 2, "signal": "strong"},
            ],
            narrative="620m to MRT, 2 primary schools within 1km.",
        )
        self.assertEqual(len(loc.connections), 2)
        self.assertEqual(loc.connections[0]["type"], "mrt")

    def test_risk_evidence_defaults(self):
        r = RiskEvidence()
        self.assertEqual(r.watchouts, [])
        self.assertEqual(r.score_adjustment, 0.0)
        self.assertEqual(r.narrative, "")

    def test_worth_viewing_result_verdict_literals(self):
        w = WorthViewingResult(
            score=86.5,
            verdict="Worth viewing",
            confidence="high",
            top_reasons=["Budget fits.", "Schools nearby."],
            top_watchouts=["MRT is moderate."],
        )
        self.assertIn(w.verdict, {"Worth viewing", "Maybe view", "Skip for now"})
        self.assertGreaterEqual(w.score, 0)
        self.assertLessEqual(w.score, 100)

    def test_avatar_preferences(self):
        avatar = HomeOSAvatar(
            label="Family HomeOS Agent",
            buyer_type="family",
            summary="Family buyer prioritizing schools.",
            preferences=HomeOSPreferences(
                flat_type="4 ROOM",
                max_price=800000.0,
                commute_priority="medium",
                school_priority="high",
                risk_tolerance="low",
                appreciation_priority="medium",
            ),
        )
        self.assertEqual(avatar.preferences.flat_type, "4 ROOM")
        self.assertEqual(avatar.preferences.school_priority, "high")

    def test_agent_questions_defaults(self):
        q = AgentQuestions()
        self.assertEqual(q.questions, [])
        self.assertEqual(q.narrative, "")


class TestHomeOSAIAgents(unittest.TestCase):
    def test_get_model_returns_test_model_by_default(self):
        from pydantic_ai.models.test import TestModel
        from app.services.homeos_ai_agents import get_model
        m = get_model()
        self.assertIsInstance(m, TestModel)

    def test_profile_agent_returns_avatar(self):
        from app.services.homeos_ai_agents import profile_agent
        result = asyncio.run(
            profile_agent.run("Family looking for 4 room under 800k near schools.")
        )
        self.assertIsInstance(result.output, HomeOSAvatar)

    def test_market_agent_returns_evidence(self):
        from app.services.homeos_ai_agents import market_agent
        result = asyncio.run(
            market_agent.run("block_id=1, flat_type=4 ROOM, max_price=800000, recent_txns=[]")
        )
        self.assertIsInstance(result.output, MarketEvidence)

    def test_location_agent_returns_evidence(self):
        from app.services.homeos_ai_agents import location_agent
        result = asyncio.run(
            location_agent.run("mrt_distance=620, schools_1km=2")
        )
        self.assertIsInstance(result.output, LocationEvidence)

    def test_risk_agent_returns_evidence(self):
        from app.services.homeos_ai_agents import risk_agent
        result = asyncio.run(
            risk_agent.run("appreciation_score=60, supply_risk=medium, risk_tolerance=low")
        )
        self.assertIsInstance(result.output, RiskEvidence)

    def test_questions_agent_returns_questions(self):
        from app.services.homeos_ai_agents import questions_agent
        result = asyncio.run(
            questions_agent.run("market_confidence=low, mrt_signal=weak")
        )
        self.assertIsInstance(result.output, AgentQuestions)


if __name__ == "__main__":
    unittest.main()
