"""Unit tests for Spec 2: commute + bus_routes tools, activating prefs, scoring watchout."""
import unittest

from pydantic import BaseModel

from app.homeos.framework.spec import AgentSpec, PrefDimension, ToolSpec
from app.homeos.models.avatar import HomeOSPreferences


class _DummyOutput(BaseModel):
    ok: bool = True


class TestPrefDimension(unittest.TestCase):
    def test_pref_dimension_defaults(self):
        dim = PrefDimension(field="work_locations", prompt="Where do you work?")
        self.assertIsNone(dim.query_key)
        self.assertIsNone(dim.default)

    def test_tool_spec_activating_prefs_defaults_empty(self):
        spec = ToolSpec(name="t", description="d", use_case="u", output_type=_DummyOutput)
        self.assertEqual(spec.activating_prefs, [])

    def test_agent_spec_activating_prefs_defaults_empty(self):
        spec = AgentSpec(name="a", description="d", system_prompt="s", output_type=_DummyOutput)
        self.assertEqual(spec.activating_prefs, [])

    def test_activating_prefs_are_per_instance(self):
        a = ToolSpec(name="t1", description="d", use_case="u", output_type=_DummyOutput)
        b = ToolSpec(name="t2", description="d", use_case="u", output_type=_DummyOutput)
        a.activating_prefs.append(PrefDimension(field="x", prompt="p"))
        self.assertEqual(b.activating_prefs, [])


class TestNewPreferences(unittest.TestCase):
    def test_defaults(self):
        prefs = HomeOSPreferences()
        self.assertEqual(prefs.work_locations, [])
        self.assertEqual(prefs.bus_reliance, "low")

    def test_work_locations_not_shared_between_instances(self):
        a, b = HomeOSPreferences(), HomeOSPreferences()
        a.work_locations.append("Raffles Place")
        self.assertEqual(b.work_locations, [])

    def test_bus_reliance_accepts_high(self):
        self.assertEqual(HomeOSPreferences(bus_reliance="high").bus_reliance, "high")


if __name__ == "__main__":
    unittest.main()
