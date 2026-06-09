"""Registers all ToolAdapters and AgentDefinitions into module-level singletons.
Call setup() once at app startup.
"""
from __future__ import annotations

from app.homeos.framework.registry import AgentRegistry, ToolRegistry
from app.homeos.mock.tools import is_mock_mode

tool_registry: ToolRegistry
agent_registry: AgentRegistry


def setup() -> None:
    global tool_registry, agent_registry

    mock = is_mock_mode()

    from app.homeos.tools.transactions import TransactionsTool
    from app.homeos.tools.proximity import ProximityTool
    from app.homeos.tools.appreciation import AppreciationTool
    from app.homeos.tools.future_dev import FutureDevTool
    from app.homeos.tools.accessibility import AccessibilityTool
    from app.homeos.tools.search import SearchTool

    tool_registry = ToolRegistry(mock=mock)
    for adapter_cls in (TransactionsTool, ProximityTool, AppreciationTool, FutureDevTool, AccessibilityTool, SearchTool):
        tool_registry.register(adapter_cls(mock=mock))

    from app.homeos.agents.profile import profile_definition
    from app.homeos.agents.market import market_definition
    from app.homeos.agents.location import location_definition
    from app.homeos.agents.risk import risk_definition
    from app.homeos.agents.questions import questions_definition

    agent_registry = AgentRegistry(tool_registry)
    for defn in (profile_definition, market_definition, location_definition, risk_definition, questions_definition):
        agent_registry.register(defn)
