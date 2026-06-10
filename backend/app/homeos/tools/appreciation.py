from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

from app.homeos.framework.spec import ToolSpec
from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_appreciation_data

if TYPE_CHECKING:
    from app.repositories.base import Repository


class AppreciationOutput(BaseModel):
    model_config = {"extra": "ignore"}
    appreciation_score: float
    risk_level: Literal["high", "medium", "low"]
    confidence_level: Literal["high", "medium", "low"] = "medium"


class AppreciationTool(ToolAdapter):
    spec = ToolSpec(
        name="appreciation",
        description="Compute an 8-factor appreciation score (0–100) for a block.",
        use_case=(
            "Use to assess long-term value growth potential and investment risk. "
            "Call when buyer has appreciation_priority or risk_tolerance set."
        ),
        output_type=AppreciationOutput,
    )

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return mock_appreciation_data(block_id or 0)
        from app.services.appreciation import appreciation
        result = appreciation(repo, block_id)
        return result or {}

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_appreciation() -> dict[str, Any]:
            """Fetch appreciation score and risk level for the current block."""
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=_prefs)

        return get_appreciation
