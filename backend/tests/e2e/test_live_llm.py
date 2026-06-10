"""Live-LLM happy path: every agent in the catalogue, tested according to its spec —
the real model must call each of the agent's declared tools.

Costs real money (one model call per tool-using agent) — opt in explicitly:
  python run_e2e.py --live
(or: LIVE_LLM=1 + AI_GATEWAY_API_KEY in env, then pytest tests/e2e/test_live_llm.py)

Agents are built with use_prefetch=False, so their declared tools are the ONLY
way to reach the data — a tool that isn't called is a failed contract.
"""
import asyncio
import os
import unittest

from tests.e2e.live_log import LiveRunLog
from tests.e2e.test_tools_e2e import _connect


class TestLiveModelToolCalls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("LIVE_LLM") != "1":
            raise unittest.SkipTest("set LIVE_LLM=1 (or run_e2e.py --live) for live model tests")
        if not os.environ.get("AI_GATEWAY_API_KEY"):
            raise unittest.SkipTest("AI_GATEWAY_API_KEY not set — no live provider")
        cls.log = LiveRunLog("agent-tool-calls")
        cls.addClassCleanup(lambda: print(f"\n  live log: {cls.log.close()}"))
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
        cls.prefs = {"max_price": 900_000}

    def _expected_call_names(self, spec) -> set[str]:
        """A tool's call name is its closure's __name__ (what the LLM sees)."""
        return {
            self.tr.get_tool(t).as_tool(self.repo, self.block_id, self.prefs).__name__
            for t in spec.tool_names
        }

    def _run_and_collect_calls(self, agent_name: str):
        from pydantic_ai.messages import ToolCallPart
        agent, prefetched = self.tr.build_agent(
            agent_name, self.repo, self.block_id, self.prefs, use_prefetch=False)
        self.assertEqual(prefetched, {})  # tools are the only data source
        result = asyncio.run(agent.run(
            "Analyse this block for the buyer. You MUST call each of your "
            "available tools to gather the data before answering."
        ))
        called = {p.tool_name for m in result.all_messages()
                  for p in m.parts if isinstance(p, ToolCallPart)}
        return result, called - {"final_result"}

    def _assert_agent_calls_its_spec_tools(self, agent_name: str):
        spec = self.tr.get_agent(agent_name)
        expected = self._expected_call_names(spec)
        result, called = self._run_and_collect_calls(agent_name)
        output_dump = result.output.model_dump()
        self.log.record("agent_output", agent=agent_name, block_id=self.block_id,
                        tool_calls=sorted(called), output=output_dump)
        self.log.section(f"{agent_name} (block {self.block_id})")
        self.log.line(f"tool calls: `{sorted(called)}`")
        self.log.block(output_dump)
        self.assertIsInstance(result.output, spec.output_type)
        missing = expected - called
        self.assertFalse(
            missing,
            f"{agent_name}: declared tools not called: {missing} (called: {called})")
        print(f"\n  {agent_name}: called {sorted(called)} ✓")

    def test_market_agent_calls_transactions(self):
        self._assert_agent_calls_its_spec_tools("market")

    def test_location_agent_calls_location_tools(self):
        self._assert_agent_calls_its_spec_tools("location")

    def test_risk_agent_calls_appreciation_future_dev_accessibility(self):
        self._assert_agent_calls_its_spec_tools("risk")

    def test_questions_agent_calls_transactions_and_proximity(self):
        self._assert_agent_calls_its_spec_tools("questions")

    def test_profile_agent_declares_no_tools(self):
        # Per spec: profile is a pure parser — nothing to call.
        spec = self.tr.get_agent("profile")
        self.assertEqual(spec.tool_names, [])
        self.assertEqual(spec.prefetch, [])

    def test_spec_coverage_is_complete(self):
        """Every tool-using agent in the catalogue has a live test above."""
        tool_using = {a["name"] for a in self.tr.describe_agents() if a["tools"]}
        self.assertEqual(tool_using, {"market", "location", "risk", "questions"})


if __name__ == "__main__":
    unittest.main()
