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


if __name__ == "__main__":
    unittest.main()
