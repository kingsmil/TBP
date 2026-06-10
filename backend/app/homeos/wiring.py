"""Registers all tool adapters and agent specs into the module-level ToolRepository singleton.
Call setup() once at app startup.
"""
from __future__ import annotations

from app.homeos.mock.tools import is_mock_mode
from app.homeos.tool_repository import ToolRepository

tool_repository: ToolRepository


def setup() -> None:
    global tool_repository

    mock = is_mock_mode()

    from app.homeos.tools.transactions import TransactionsTool
    from app.homeos.tools.proximity import ProximityTool
    from app.homeos.tools.appreciation import AppreciationTool
    from app.homeos.tools.future_dev import FutureDevTool
    from app.homeos.tools.accessibility import AccessibilityTool
    from app.homeos.tools.search import SearchTool
    from app.homeos.tools.commute import CommuteTool
    from app.homeos.tools.bus_routes import BusRoutesTool
    from app.homeos.tools.lifestyle_score import LifestyleScoreTool

    tool_repository = ToolRepository(mock=mock)
    for cls in (TransactionsTool, ProximityTool, AppreciationTool,
                FutureDevTool, AccessibilityTool, SearchTool,
                CommuteTool, BusRoutesTool, LifestyleScoreTool):
        tool_repository.register_tool(cls(mock=mock))

    from app.homeos.agents.profile import profile_definition
    from app.homeos.agents.market import market_definition
    from app.homeos.agents.location import location_definition
    from app.homeos.agents.risk import risk_definition
    from app.homeos.agents.questions import questions_definition
    from app.homeos.agents.lifestyle import lifestyle_definition

    for spec in (profile_definition, market_definition, location_definition,
                 risk_definition, questions_definition, lifestyle_definition):
        tool_repository.register_agent(spec)
