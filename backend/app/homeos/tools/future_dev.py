from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

from app.homeos.framework.spec import ToolSpec
from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_future_dev_data

if TYPE_CHECKING:
    from app.repositories.base import Repository


class FutureMrtInfo(BaseModel):
    model_config = {"extra": "ignore"}
    station_name: str | None = None
    line_name: str | None = None
    opening_year: int | None = None
    distance_m: float | None = None
    future_transport_growth_score: float | None = None


class FutureSupplyInfo(BaseModel):
    model_config = {"extra": "ignore"}
    future_bto_count: int = 0
    supply_pressure_pct: float = 0.0
    supply_risk_level: Literal["high", "medium", "low"] = "low"


class FutureDevOutput(BaseModel):
    model_config = {"extra": "ignore"}
    future_mrt: FutureMrtInfo = FutureMrtInfo()
    future_supply: FutureSupplyInfo = FutureSupplyInfo()


class FutureDevTool(ToolAdapter):
    spec = ToolSpec(
        name="future_dev",
        description="Fetch upcoming MRT stations and nearby BTO supply pipeline for a block.",
        use_case=(
            "Use to evaluate transport growth potential and supply risk from BTO projects. "
            "Call when buyer has appreciation_priority or risk_tolerance set."
        ),
        output_type=FutureDevOutput,
    )

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return mock_future_dev_data(block_id or 0)
        from app.services.future_dev import future_mrt, future_supply
        return {
            "future_mrt": future_mrt(repo, block_id) or {},
            "future_supply": future_supply(repo, block_id) or {},
        }

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_future_dev() -> dict[str, Any]:
            """Fetch future MRT and BTO supply data for the current block."""
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=_prefs)

        return get_future_dev
