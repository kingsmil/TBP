"""End-to-end tests: tools and agents run against the REAL PostGIS database
from docker-compose, with whatever data `setup.py` seeded into it.

Skipped automatically when DATABASE_URL is unset or the database is unreachable,
so the regular unit suite stays green without Docker.

Run via:  python run_e2e.py   (from the estate-finder root)
or:       DATABASE_URL=postgresql://hdbmatch:hdbmatch@localhost:5432/hdbmatch \
          pytest tests/e2e/ -v
"""
import asyncio
import os
import unittest
from unittest.mock import patch

# Same guard as tests/integration/test_agents.py — never make live LLM calls.
_env_patch = patch.dict(os.environ, {"LLM_PROVIDER": "test", "AI_GATEWAY_API_KEY": ""})


def _connect():
    """Return (engine, PostgisRepository) or raise unittest.SkipTest."""
    if not os.environ.get("DATABASE_URL"):
        raise unittest.SkipTest("DATABASE_URL not set — E2E tests need the compose DB")
    try:
        from app.db.session import get_engine
        from app.repositories.postgis import PostgisRepository
        engine = get_engine()
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return engine, PostgisRepository(engine)
    except unittest.SkipTest:
        raise
    except Exception as exc:
        raise unittest.SkipTest(f"PostGIS unreachable: {exc}")


class TestToolsE2E(unittest.TestCase):
    """Every tool adapter fetches from the live PostGIS repo and the result
    validates against the tool's declared output schema."""

    @classmethod
    def setUpClass(cls):
        _env_patch.start()
        cls.addClassCleanup(_env_patch.stop)
        cls.engine, cls.repo = _connect()

        # Pick the block with the most transactions so assertions are meaningful.
        with cls.engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT block_id, count(*) AS n FROM hdb_transactions "
                "GROUP BY block_id ORDER BY n DESC LIMIT 1"
            ).fetchone()
        if row is None:
            raise unittest.SkipTest("hdb_transactions is empty — run `python setup.py` to seed")
        cls.block_id = row[0]
        cls.prefs = {"max_price": 900_000}

    def test_transactions_tool_returns_real_market_data(self):
        from app.homeos.tools.transactions import TransactionsTool
        tool = TransactionsTool()
        result = tool.fetch(self.repo, self.block_id, self.prefs)
        output = tool.spec.output_type.model_validate(result)
        self.assertGreater(output.transaction_count, 0)
        self.assertIsNotNone(output.median_price)
        self.assertGreater(output.median_price, 0)
        self.assertIn(output.budget_signal, ("within_budget", "above_budget"))

    def test_proximity_tool_returns_real_connections(self):
        from app.homeos.tools.proximity import ProximityTool
        tool = ProximityTool()
        result = tool.fetch(self.repo, self.block_id, self.prefs)
        output = tool.spec.output_type.model_validate(result)
        types = {c.type for c in output.connections}
        self.assertIn("mrt", types)

    def test_appreciation_tool_scores_real_block(self):
        from app.homeos.tools.appreciation import AppreciationTool
        tool = AppreciationTool()
        result = tool.fetch(self.repo, self.block_id, self.prefs)
        output = tool.spec.output_type.model_validate(result)
        self.assertGreaterEqual(output.appreciation_score, 0.0)
        self.assertLessEqual(output.appreciation_score, 100.0)

    def test_future_dev_tool_validates_on_real_block(self):
        from app.homeos.tools.future_dev import FutureDevTool
        tool = FutureDevTool()
        result = tool.fetch(self.repo, self.block_id, self.prefs)
        output = tool.spec.output_type.model_validate(result)
        self.assertGreaterEqual(output.future_supply.future_bto_count, 0)

    def test_accessibility_tool_validates_on_real_block(self):
        from app.homeos.tools.accessibility import AccessibilityTool
        tool = AccessibilityTool()
        result = tool.fetch(self.repo, self.block_id, self.prefs)
        output = tool.spec.output_type.model_validate(result)
        self.assertGreaterEqual(output.combined_score, 0.0)

    def test_search_tool_finds_real_blocks(self):
        from app.homeos.tools.search import SearchTool
        tool = SearchTool()
        result = tool.fetch(self.repo, None, {"max_price": 900_000})
        output = tool.spec.output_type.model_validate(result)
        self.assertGreater(len(output.results), 0)
        first = output.results[0]
        self.assertTrue(first.town)
        self.assertGreater(first.block_id, 0)


class TestAgentsE2E(unittest.TestCase):
    """Agents built via ToolRepository prefetch REAL PostGIS data into their
    system prompts. The LLM itself is TestModel (offline) — what's end-to-end
    here is the data path: PostGIS → services → tools → agent context."""

    @classmethod
    def setUpClass(cls):
        _env_patch.start()
        cls.addClassCleanup(_env_patch.stop)
        cls.engine, cls.repo = _connect()
        from app.homeos.wiring import setup
        setup()
        import app.homeos.wiring as wiring_mod
        cls.tr = wiring_mod.tool_repository

        with cls.engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT block_id, count(*) AS n FROM hdb_transactions "
                "GROUP BY block_id ORDER BY n DESC LIMIT 1"
            ).fetchone()
        if row is None:
            raise unittest.SkipTest("hdb_transactions is empty — run `python setup.py` to seed")
        cls.block_id = row[0]
        cls.prefs = {"max_price": 900_000}

    def _run(self, agent_name: str, prompt: str):
        async def go():
            agent, prefetched = self.tr.build_agent(agent_name, self.repo, self.block_id, self.prefs)
            result = await agent.run(prompt)
            return result.output, prefetched
        return asyncio.run(go())

    def test_market_agent_prefetches_real_transactions(self):
        _, prefetched = self._run("market", "Analyse the market for this block.")
        txns = prefetched["transactions"]
        self.assertGreater(txns["transaction_count"], 0)
        self.assertIsNotNone(txns["median_price"])

    def test_location_agent_prefetches_real_proximity(self):
        _, prefetched = self._run("location", "Summarise the location.")
        connections = prefetched["proximity"]["connections"]
        self.assertTrue(any(c["type"] == "mrt" for c in connections))

    def test_risk_agent_prefetches_real_appreciation_and_future_dev(self):
        _, prefetched = self._run("risk", "Assess risk for this block.")
        self.assertIn("appreciation_score", prefetched["appreciation"])
        self.assertIn("future_supply", prefetched["future_dev"])


if __name__ == "__main__":
    unittest.main()
