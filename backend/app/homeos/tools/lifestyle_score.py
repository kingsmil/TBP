from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from app.homeos.framework.spec import ToolSpec
from app.homeos.framework.tool import ToolAdapter

if TYPE_CHECKING:
    from app.repositories.base import Repository


class LifestyleScoreOutput(BaseModel):
    model_config = {"extra": "ignore"}
    lifestyle_score: float | None = None
    factors: dict[str, float] = {}


class LifestyleScoreTool(ToolAdapter):
    spec = ToolSpec(
        name="lifestyle_score",
        description="Compute the blended lifestyle score (0-100) for a block.",
        use_case=(
            "Call to get the composite lifestyle fit score and per-factor breakdown "
            "(transport, schools, affordability, commute)."
        ),
        output_type=LifestyleScoreOutput,
    )

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return {"lifestyle_score": 72.0, "factors": {"transport": 60.0, "schools": 80.0, "affordability": 75.0}}
        if block_id is None:
            return {"lifestyle_score": None, "factors": {}}
        from app.services.lifestyle import block_lifestyle
        from app.homeos.tools.commute import _resolve_station
        from app.services.commute.models import Destination
        from app.services.commute.provider import HeuristicCommuteProvider

        provider = None
        destinations = None
        workplaces = prefs.get("work_locations") or []
        if workplaces:
            stations = list(repo.mrt_stations(status="operational"))
            if stations:
                provider = HeuristicCommuteProvider(stations)
                destinations = [
                    Destination(name=s.station_name, point=s.point, visits_per_week=5)
                    for name in workplaces
                    if (s := _resolve_station(str(name), stations)) is not None
                ] or None

        result = block_lifestyle(repo, block_id, provider, destinations)
        return result or {"lifestyle_score": None, "factors": {}}

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_lifestyle_score() -> dict[str, Any]:
            """Compute the blended lifestyle score and per-factor breakdown for this block."""
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=_prefs)

        return get_lifestyle_score
