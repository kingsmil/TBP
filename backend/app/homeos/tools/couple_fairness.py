from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from app.homeos.framework.spec import ToolSpec
from app.homeos.framework.tool import ToolAdapter

if TYPE_CHECKING:
    from app.repositories.base import Repository


class CoupleFairnessOutput(BaseModel):
    model_config = {"extra": "ignore"}
    available: bool
    fairness_score: float | None = None
    person_a_weekly_minutes: float | None = None
    person_b_weekly_minutes: float | None = None
    combined_weekly_minutes: float | None = None


class CoupleFairnessTool(ToolAdapter):
    spec = ToolSpec(
        name="couple_fairness",
        description="Compute commute fairness score for a couple with separate workplaces.",
        use_case=(
            "Use when buyer_type is 'couple' and both work_locations and partner_work_locations "
            "are provided. Returns a fairness score (0-100) where 100 = perfectly balanced commutes."
        ),
        output_type=CoupleFairnessOutput,
    )

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            partner_locs = prefs.get("partner_work_locations") or []
            if not partner_locs:
                return {"available": False, "fairness_score": None,
                        "person_a_weekly_minutes": None, "person_b_weekly_minutes": None,
                        "combined_weekly_minutes": None}
            return {"available": True, "fairness_score": 78.0,
                    "person_a_weekly_minutes": 180.0, "person_b_weekly_minutes": 210.0,
                    "combined_weekly_minutes": 390.0}

        work_a = prefs.get("work_locations") or []
        work_b = prefs.get("partner_work_locations") or []
        if not work_a or not work_b or block_id is None:
            return {"available": False, "fairness_score": None,
                    "person_a_weekly_minutes": None, "person_b_weekly_minutes": None,
                    "combined_weekly_minutes": None}

        block = repo.block(block_id)
        if block is None:
            return {"available": False, "fairness_score": None,
                    "person_a_weekly_minutes": None, "person_b_weekly_minutes": None,
                    "combined_weekly_minutes": None}

        from app.homeos.tools.commute import _resolve_station
        from app.services.commute.models import Destination
        from app.services.commute.provider import HeuristicCommuteProvider
        from app.services.commute.optimizer import commute_burden
        from app.services.commute.couple import fairness_score

        stations = list(repo.mrt_stations(status="operational"))
        if not stations:
            return {"available": False, "fairness_score": None,
                    "person_a_weekly_minutes": None, "person_b_weekly_minutes": None,
                    "combined_weekly_minutes": None}

        provider = HeuristicCommuteProvider(stations)

        def _to_destinations(names: list[str]) -> list[Destination]:
            return [
                Destination(name=s.station_name, point=s.point, visits_per_week=5)
                for name in names
                if (s := _resolve_station(str(name), stations)) is not None
            ]

        dests_a = _to_destinations(work_a)
        dests_b = _to_destinations(work_b)
        if not dests_a or not dests_b:
            return {"available": False, "fairness_score": None,
                    "person_a_weekly_minutes": None, "person_b_weekly_minutes": None,
                    "combined_weekly_minutes": None}

        wk_a = commute_burden(provider, block.point, dests_a)["weekly_minutes"]
        wk_b = commute_burden(provider, block.point, dests_b)["weekly_minutes"]
        return {
            "available": True,
            "fairness_score": fairness_score(wk_a, wk_b),
            "person_a_weekly_minutes": round(wk_a, 1),
            "person_b_weekly_minutes": round(wk_b, 1),
            "combined_weekly_minutes": round(wk_a + wk_b, 1),
        }

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_couple_fairness() -> dict[str, Any]:
            """Compute commute fairness score for a couple with separate workplaces (0-100, higher = more balanced)."""
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=_prefs)

        return get_couple_fairness
