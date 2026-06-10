from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from app.homeos.framework.spec import ToolSpec
from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_accessibility_data

if TYPE_CHECKING:
    from app.repositories.base import Repository


class AccessibilityRaw(BaseModel):
    model_config = {"extra": "ignore"}
    nearest_mrt_distance_m: float | None = None
    nearest_bus_distance_m: float | None = None
    bus_stops_within_400m: int = 0
    schools_within_1km: int = 0


class AccessibilityOutput(BaseModel):
    model_config = {"extra": "ignore"}
    mrt_score: float = 0.0
    bus_score: float = 0.0
    school_score: float = 0.0
    combined_score: float = 0.0
    raw: AccessibilityRaw | None = None
    # mock-mode keys (real mode omits them; extra keys are ignored either way)
    bus_stops_within_500m: int | None = None
    nearest_bus_distance_m: float | None = None


class AccessibilityTool(ToolAdapter):
    spec = ToolSpec(
        name="accessibility",
        description="Fetch MRT, bus, and school accessibility scores for a block.",
        use_case=(
            "Use to assess overall transport and amenity convenience. "
            "Call when buyer has no car or commute_priority is high."
        ),
        output_type=AccessibilityOutput,
    )

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return mock_accessibility_data(block_id or 0)
        from app.services.accessibility import block_accessibility
        return block_accessibility(repo, block_id) or {}

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_accessibility() -> dict[str, Any]:
            """Fetch bus stop accessibility for the current block."""
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=_prefs)

        return get_accessibility
