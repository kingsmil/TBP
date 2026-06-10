"""Live-LLM happy path: ONE real model call proving the agent actually invokes its tools.

Costs real money — opt in explicitly:  python run_e2e.py --live
(or: LIVE_LLM=1 + provider key in env, then pytest tests/e2e/test_live_llm.py)

Uses the `questions` agent because it has tools but NO prefetch — the only way
the model can see transaction/proximity data is by calling the tools itself.
"""
import asyncio
import os
import unittest

from tests.e2e.test_tools_e2e import _connect


class TestLiveModelToolCalls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("LIVE_LLM") != "1":
            raise unittest.SkipTest("set LIVE_LLM=1 (or run_e2e.py --live) for live model tests")
        if not os.environ.get("AI_GATEWAY_API_KEY"):
            raise unittest.SkipTest("AI_GATEWAY_API_KEY not set — no live provider")
        cls.engine, cls.repo = _connect()
        from app.homeos.wiring import setup
        setup()
        import app.homeos.wiring as wiring_mod
        cls.tr = wiring_mod.tool_repository
        with cls.engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT block_id FROM hdb_transactions GROUP BY block_id "
                "ORDER BY count(*) DESC LIMIT 1"
            ).fetchone()
        cls.block_id = row[0]

    def test_live_model_calls_tools_and_returns_questions(self):
        from pydantic_ai.messages import ToolCallPart
        from app.homeos.models.evidence import AgentQuestions

        agent, prefetched = self.tr.build_agent(
            "questions", self.repo, self.block_id, {"max_price": 900_000})
        self.assertEqual(prefetched, {})  # no prefetch — tools are the only data source

        result = asyncio.run(agent.run(
            "Generate due-diligence questions for this block. "
            "First fetch the transaction and proximity data with your tools."
        ))

        # Happy path: structured output + at least one real tool call.
        self.assertIsInstance(result.output, AgentQuestions)
        self.assertGreaterEqual(len(result.output.questions), 1)
        calls = [p.tool_name for m in result.all_messages()
                 for p in m.parts if isinstance(p, ToolCallPart)]
        data_calls = [c for c in calls if c in ("get_transactions", "get_proximity")]
        self.assertTrue(data_calls, f"model never called a data tool (calls seen: {calls})")
        print(f"\n  live model tool calls: {data_calls}")
        print(f"  first question: {result.output.questions[0]!r}")


if __name__ == "__main__":
    unittest.main()
