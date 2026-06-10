"""Integration tests: build and run each agent via ToolRepository.
Uses the seeded in-memory repo and TestModel (no API key needed).
"""
import asyncio
import os
import unittest
from unittest.mock import patch

from app.data.seed import build_seeded_repo
from app.homeos.models.evidence import MarketEvidence, LocationEvidence, RiskEvidence, AgentQuestions
from app.homeos.models.avatar import HomeOSAvatar

# Force the offline TestModel regardless of ambient env vars. get_model() uses the
# live gateway whenever AI_GATEWAY_API_KEY is set (even with LLM_PROVIDER=test), so
# both must be pinned or these tests would make real, billed LLM calls in CI.
_env_patch = patch.dict(os.environ, {"LLM_PROVIDER": "test", "AI_GATEWAY_API_KEY": ""})


class TestAgentsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _env_patch.start()
        cls.addClassCleanup(_env_patch.stop)
        from app.homeos.wiring import setup
        setup()
        import app.homeos.wiring as wiring_mod
        cls.tr = wiring_mod.tool_repository
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=4, months=6)
        cls.block_id = list(cls.repo.blocks())[0].block_id
        cls.prefs = {"max_price": 700_000, "flat_type": "4 ROOM"}

    def _run(self, agent_name: str, block_id, prefs: dict, prompt: str):
        async def go():
            agent, prefetched = self.tr.build_agent(agent_name, self.repo, block_id, prefs)
            result = await agent.run(prompt)
            return result.output, prefetched
        return asyncio.run(go())

    def test_market_agent_returns_market_evidence_instance(self):
        output, prefetched = self._run(
            "market", self.block_id, self.prefs,
            "Analyse the market for this block."
        )
        self.assertIsInstance(output, MarketEvidence)
        self.assertIn("transactions", prefetched)

    def test_location_agent_returns_location_evidence_instance(self):
        output, prefetched = self._run(
            "location", self.block_id, self.prefs,
            "Summarise the location for this block."
        )
        self.assertIsInstance(output, LocationEvidence)
        self.assertIn("proximity", prefetched)

    def test_risk_agent_returns_risk_evidence_instance(self):
        output, prefetched = self._run(
            "risk", self.block_id, self.prefs,
            "Assess risk and value for this block."
        )
        self.assertIsInstance(output, RiskEvidence)
        self.assertIn("appreciation", prefetched)
        self.assertIn("future_dev", prefetched)

    def test_questions_agent_returns_agent_questions_instance(self):
        output, prefetched = self._run(
            "questions", self.block_id, self.prefs,
            "Generate due-diligence questions for this block."
        )
        self.assertIsInstance(output, AgentQuestions)

    def test_profile_agent_returns_home_os_avatar_instance(self):
        output, _ = self._run(
            "profile", None, {},
            "Young couple, 4-room flat, budget $700k, near good schools."
        )
        self.assertIsInstance(output, HomeOSAvatar)

    def test_tool_repository_describe_tools_includes_all_metadata(self):
        catalogue = self.tr.describe_tools()
        names = {e["name"] for e in catalogue}
        self.assertIn("transactions", names)
        self.assertIn("appreciation", names)
        self.assertIn("search", names)
        for entry in catalogue:
            with self.subTest(tool=entry["name"]):
                self.assertIn("use_case", entry)
                self.assertIn("output_schema", entry)
                self.assertIn("properties", entry["output_schema"])

    def test_agents_using_tool_is_accurate(self):
        using_txns = self.tr.agents_using_tool("transactions")
        self.assertIn("market", using_txns)
        self.assertIn("questions", using_txns)

        using_appr = self.tr.agents_using_tool("appreciation")
        self.assertIn("risk", using_appr)
        self.assertNotIn("market", using_appr)

    def test_tools_for_agent_returns_correct_adapters(self):
        risk_tools = self.tr.tools_for_agent("risk")
        risk_tool_names = {t.spec.name for t in risk_tools}
        self.assertEqual(risk_tool_names, {"appreciation", "future_dev", "accessibility"})


if __name__ == "__main__":
    unittest.main()
