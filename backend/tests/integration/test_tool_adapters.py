"""Integration tests: each tool adapter fetches real data from the seeded in-memory repo
and the result validates cleanly into the tool's declared output_type."""
import unittest

from app.data.seed import build_seeded_repo


class TestToolAdaptersIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=4, months=6)
        cls.block_id = list(cls.repo.blocks())[0].block_id
        cls.prefs = {"max_price": 700_000, "flat_type": "4 ROOM"}

    def _fetch_and_validate(self, tool_cls, block_id):
        tool = tool_cls()
        result = tool.fetch(self.repo, block_id, self.prefs)
        validated = tool.spec.output_type.model_validate(result)
        return validated

    def test_transactions_tool_output_validates(self):
        from app.homeos.tools.transactions import TransactionsTool, TransactionsOutput
        output = self._fetch_and_validate(TransactionsTool, self.block_id)
        self.assertIsInstance(output, TransactionsOutput)
        self.assertGreaterEqual(output.transaction_count, 0)
        self.assertIn(output.budget_signal, ("within_budget", "above_budget", "unknown"))
        self.assertIn(output.confidence, ("high", "medium", "low"))

    def test_proximity_tool_output_validates(self):
        from app.homeos.tools.proximity import ProximityTool, ProximityOutput
        output = self._fetch_and_validate(ProximityTool, self.block_id)
        self.assertIsInstance(output, ProximityOutput)
        self.assertIsInstance(output.connections, list)
        types = {c.type for c in output.connections}
        self.assertIn("mrt", types)

    def test_appreciation_tool_output_validates(self):
        from app.homeos.tools.appreciation import AppreciationTool, AppreciationOutput
        output = self._fetch_and_validate(AppreciationTool, self.block_id)
        self.assertIsInstance(output, AppreciationOutput)
        self.assertGreaterEqual(output.appreciation_score, 0.0)
        self.assertLessEqual(output.appreciation_score, 100.0)
        self.assertIn(output.risk_level, ("high", "medium", "low"))

    def test_future_dev_tool_output_validates(self):
        from app.homeos.tools.future_dev import FutureDevTool, FutureDevOutput
        output = self._fetch_and_validate(FutureDevTool, self.block_id)
        self.assertIsInstance(output, FutureDevOutput)
        self.assertGreaterEqual(output.future_supply.future_bto_count, 0)

    def test_accessibility_tool_output_validates(self):
        from app.homeos.tools.accessibility import AccessibilityTool, AccessibilityOutput
        output = self._fetch_and_validate(AccessibilityTool, self.block_id)
        self.assertIsInstance(output, AccessibilityOutput)
        self.assertGreaterEqual(output.combined_score, 0.0)

    def test_search_tool_output_validates(self):
        from app.homeos.tools.search import SearchTool, SearchOutput
        tool = SearchTool()
        result = tool.fetch(self.repo, None, self.prefs)
        output = tool.spec.output_type.model_validate(result)
        self.assertIsInstance(output, SearchOutput)
        self.assertGreater(len(output.results), 0)
        self.assertIsInstance(output.results[0].town, str)

    def test_commute_tool_output_validates(self):
        from app.homeos.tools.commute import CommuteTool, CommuteOutput
        tool = CommuteTool()
        result = tool.fetch(self.repo, self.block_id,
                            {**self.prefs, "work_locations": ["MRT-1", "Nowhere Special"]})
        output = CommuteOutput.model_validate(result)
        self.assertTrue(output.available)
        resolved = {d.name: d.resolved for d in output.destinations}
        self.assertTrue(resolved["MRT-1"])
        self.assertFalse(resolved["Nowhere Special"])
        self.assertIsNotNone(output.worst_commute_min)

    def test_commute_tool_without_work_locations_is_unavailable(self):
        from app.homeos.tools.commute import CommuteTool, CommuteOutput
        output = CommuteOutput.model_validate(
            CommuteTool().fetch(self.repo, self.block_id, self.prefs))
        self.assertFalse(output.available)
        self.assertEqual(output.destinations, [])

    def test_bus_routes_tool_with_seeded_routes(self):
        from app.homeos.tools.bus_routes import BusRoutesTool, BusRoutesOutput
        prox = self.repo.proximity(self.block_id)
        code = prox.nearest_bus_stop_code
        self.assertIsNotNone(code)  # seed generator creates 3 stops/area
        self.repo.add_bus_routes([
            {"service_no": "901", "direction": 1, "stop_sequence": 1, "bus_stop_code": code},
            {"service_no": "901", "direction": 1, "stop_sequence": 2,
             "bus_stop_code": next(s.bus_stop_code for s in self.repo.bus_stops()
                                   if s.bus_stop_code != code)},
        ])
        output = BusRoutesOutput.model_validate(
            BusRoutesTool().fetch(self.repo, self.block_id, {}))
        self.assertTrue(output.available)
        self.assertEqual(output.services[0].service_no, "901")
        self.assertGreaterEqual(output.services[0].stops_reachable, 1)

    def test_bus_routes_tool_without_routes_is_honestly_unavailable(self):
        from app.homeos.tools.bus_routes import BusRoutesTool, BusRoutesOutput
        repo, _ = build_seeded_repo(seed=7, blocks_per_area=2, months=3)
        block_id = list(repo.blocks())[0].block_id
        output = BusRoutesOutput.model_validate(BusRoutesTool().fetch(repo, block_id, {}))
        self.assertFalse(output.available)
        self.assertEqual(output.services, [])

    def test_all_tool_outputs_parse_via_spec_output_type(self):
        """Each tool's declared output_type must cleanly parse its own fetch() result."""
        from app.homeos.tools.transactions import TransactionsTool
        from app.homeos.tools.proximity import ProximityTool
        from app.homeos.tools.appreciation import AppreciationTool
        from app.homeos.tools.future_dev import FutureDevTool
        from app.homeos.tools.accessibility import AccessibilityTool
        from app.homeos.tools.search import SearchTool
        from app.homeos.tools.commute import CommuteTool
        from app.homeos.tools.bus_routes import BusRoutesTool

        pairs = [
            (TransactionsTool, self.block_id),
            (ProximityTool, self.block_id),
            (AppreciationTool, self.block_id),
            (FutureDevTool, self.block_id),
            (AccessibilityTool, self.block_id),
            (SearchTool, None),
            (CommuteTool, self.block_id),
            (BusRoutesTool, self.block_id),
        ]
        for cls, block_id in pairs:
            with self.subTest(tool=cls.spec.name):
                tool = cls()
                result = tool.fetch(self.repo, block_id, self.prefs)
                validated = tool.spec.output_type.model_validate(result)
                self.assertIsNotNone(validated)


if __name__ == "__main__":
    unittest.main()
