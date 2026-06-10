import unittest
from pydantic import BaseModel


class TestToolSpec(unittest.TestCase):
    def test_toolspec_stores_all_fields(self):
        from app.homeos.framework.spec import ToolSpec

        class Out(BaseModel):
            value: int

        spec = ToolSpec(
            name="my_tool",
            description="Fetches something.",
            use_case="Use when you need something.",
            output_type=Out,
        )
        self.assertEqual(spec.name, "my_tool")
        self.assertEqual(spec.use_case, "Use when you need something.")
        self.assertIs(spec.output_type, Out)

    def test_toolspec_rejects_non_basemodel_output_type(self):
        from app.homeos.framework.spec import ToolSpec
        with self.assertRaises(TypeError):
            ToolSpec(name="x", description="x", use_case="x", output_type=dict)


class TestAgentSpec(unittest.TestCase):
    def test_agentspec_stores_all_fields(self):
        from app.homeos.framework.spec import AgentSpec

        class Out(BaseModel):
            result: str

        spec = AgentSpec(
            name="my_agent",
            description="Does market analysis.",
            system_prompt="You are an analyst.",
            output_type=Out,
            tool_names=["transactions"],
            prefetch=["transactions"],
        )
        self.assertEqual(spec.name, "my_agent")
        self.assertEqual(spec.description, "Does market analysis.")
        self.assertEqual(spec.tool_names, ["transactions"])

    def test_agentspec_defaults_to_empty_lists(self):
        from app.homeos.framework.spec import AgentSpec

        class Out(BaseModel):
            x: int

        spec = AgentSpec(name="a", description="b", system_prompt="c", output_type=Out)
        self.assertEqual(spec.tool_names, [])
        self.assertEqual(spec.prefetch, [])


class TestToolAdapterSpec(unittest.TestCase):
    def test_concrete_tool_with_spec_attribute(self):
        from app.homeos.framework.tool import ToolAdapter
        from app.homeos.framework.spec import ToolSpec

        class Out(BaseModel):
            value: int

        class MyTool(ToolAdapter):
            spec = ToolSpec(
                name="my_tool",
                description="Does something.",
                use_case="Use when X.",
                output_type=Out,
            )

            def fetch(self, repo, block_id, prefs):
                return {"value": 1}

            def as_tool(self, repo, block_id, prefs):
                def get():
                    return {"value": 1}
                return get

        t = MyTool()
        self.assertEqual(t.name, "my_tool")
        self.assertEqual(t.description, "Does something.")
        self.assertEqual(t.spec.use_case, "Use when X.")


class TestToolRepository(unittest.TestCase):
    def _build_repo_with_fake_tool(self):
        from app.homeos.tool_repository import ToolRepository
        from app.homeos.framework.tool import ToolAdapter
        from app.homeos.framework.spec import ToolSpec

        class FakeOutput(BaseModel):
            value: int

        class FakeTool(ToolAdapter):
            spec = ToolSpec(
                name="fake",
                description="A fake tool.",
                use_case="Use when testing.",
                output_type=FakeOutput,
            )
            def fetch(self, repo, block_id, prefs):
                return {"value": 42}
            def as_tool(self, repo, block_id, prefs):
                def fake():
                    return {"value": 42}
                return fake

        tr = ToolRepository()
        tr.register_tool(FakeTool())
        return tr

    def test_register_and_get_tool(self):
        tr = self._build_repo_with_fake_tool()
        tool = tr.get_tool("fake")
        self.assertEqual(tool.spec.name, "fake")

    def test_get_unknown_tool_raises_key_error(self):
        from app.homeos.tool_repository import ToolRepository
        tr = ToolRepository()
        with self.assertRaises(KeyError):
            tr.get_tool("nonexistent")

    def test_describe_tools_returns_catalogue_entries(self):
        tr = self._build_repo_with_fake_tool()
        catalogue = tr.describe_tools()
        self.assertEqual(len(catalogue), 1)
        entry = catalogue[0]
        self.assertEqual(entry["name"], "fake")
        self.assertIn("description", entry)
        self.assertIn("use_case", entry)
        self.assertIn("output_schema", entry)
        self.assertIsInstance(entry["output_schema"], dict)

    def test_register_agent_validates_tool_names_exist(self):
        from app.homeos.tool_repository import ToolRepository
        from app.homeos.framework.spec import AgentSpec

        class Out(BaseModel):
            x: int

        tr = ToolRepository()
        spec = AgentSpec(
            name="market",
            description="Market analyst.",
            system_prompt="Analyse.",
            output_type=Out,
            tool_names=["nonexistent_tool"],
            prefetch=[],
        )
        with self.assertRaises(KeyError):
            tr.register_agent(spec)

    def test_tools_for_agent_returns_adapters(self):
        tr = self._build_repo_with_fake_tool()
        from app.homeos.framework.spec import AgentSpec

        class Out(BaseModel):
            x: int

        tr.register_agent(AgentSpec(
            name="myagent",
            description="Uses fake.",
            system_prompt="Do stuff.",
            output_type=Out,
            tool_names=["fake"],
            prefetch=["fake"],
        ))
        tools = tr.tools_for_agent("myagent")
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].spec.name, "fake")

    def test_agents_using_tool_lists_agent_names(self):
        tr = self._build_repo_with_fake_tool()
        from app.homeos.framework.spec import AgentSpec

        class Out(BaseModel):
            x: int

        tr.register_agent(AgentSpec(
            name="myagent",
            description="Uses fake.",
            system_prompt="Do stuff.",
            output_type=Out,
            tool_names=["fake"],
            prefetch=[],
        ))
        agents = tr.agents_using_tool("fake")
        self.assertIn("myagent", agents)

    def test_describe_agents_returns_catalogue(self):
        tr = self._build_repo_with_fake_tool()
        from app.homeos.framework.spec import AgentSpec

        class Out(BaseModel):
            x: int

        tr.register_agent(AgentSpec(
            name="myagent",
            description="Uses fake.",
            system_prompt="Do stuff.",
            output_type=Out,
            tool_names=["fake"],
            prefetch=[],
        ))
        agents = tr.describe_agents()
        self.assertEqual(len(agents), 1)
        self.assertIn("description", agents[0])
        self.assertIn("tools", agents[0])


class TestExistingToolSpecs(unittest.TestCase):
    def _all_tool_classes(self):
        from app.homeos.tools.transactions import TransactionsTool
        from app.homeos.tools.proximity import ProximityTool
        from app.homeos.tools.appreciation import AppreciationTool
        from app.homeos.tools.future_dev import FutureDevTool
        from app.homeos.tools.accessibility import AccessibilityTool
        from app.homeos.tools.search import SearchTool
        return [
            TransactionsTool, ProximityTool, AppreciationTool,
            FutureDevTool, AccessibilityTool, SearchTool,
        ]

    def test_all_tools_have_spec(self):
        from app.homeos.framework.spec import ToolSpec
        for cls in self._all_tool_classes():
            with self.subTest(cls=cls.__name__):
                self.assertIsInstance(cls.spec, ToolSpec)

    def test_all_tools_have_non_empty_use_case(self):
        for cls in self._all_tool_classes():
            with self.subTest(cls=cls.__name__):
                self.assertTrue(
                    cls.spec.use_case,
                    f"{cls.__name__}.spec.use_case is empty"
                )

    def test_all_tools_have_basemodel_output_type(self):
        from pydantic import BaseModel
        for cls in self._all_tool_classes():
            with self.subTest(cls=cls.__name__):
                self.assertTrue(
                    issubclass(cls.spec.output_type, BaseModel),
                    f"{cls.__name__}.spec.output_type is not a BaseModel subclass"
                )


class TestAgentMigration(unittest.TestCase):
    def test_all_agent_definitions_are_agentspec(self):
        from app.homeos.framework.spec import AgentSpec
        from app.homeos.agents.profile import profile_definition
        from app.homeos.agents.market import market_definition
        from app.homeos.agents.location import location_definition
        from app.homeos.agents.risk import risk_definition
        from app.homeos.agents.questions import questions_definition
        for defn in (profile_definition, market_definition, location_definition,
                     risk_definition, questions_definition):
            with self.subTest(name=defn.name):
                self.assertIsInstance(defn, AgentSpec)
                self.assertTrue(defn.description, f"{defn.name} has empty description")

    def test_market_agent_has_correct_tools(self):
        from app.homeos.agents.market import market_definition
        self.assertIn("transactions", market_definition.tool_names)
        self.assertIn("transactions", market_definition.prefetch)

    def test_risk_agent_has_correct_tools(self):
        from app.homeos.agents.risk import risk_definition
        for t in ("appreciation", "future_dev", "accessibility"):
            self.assertIn(t, risk_definition.tool_names)
        self.assertIn("appreciation", risk_definition.prefetch)
        self.assertIn("future_dev", risk_definition.prefetch)


if __name__ == "__main__":
    unittest.main()
