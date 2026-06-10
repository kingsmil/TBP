from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from app.core.models import MrtStation
from app.homeos.framework.spec import PrefDimension, ToolSpec
from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_commute_data
from app.services.commute.provider import HeuristicCommuteProvider

if TYPE_CHECKING:
    from app.repositories.base import Repository


class CommuteDestination(BaseModel):
    model_config = {"extra": "ignore"}
    name: str
    resolved: bool
    travel_min: float | None = None
    transfers: int | None = None
    mode: str | None = None


class CommuteOutput(BaseModel):
    model_config = {"extra": "ignore"}
    available: bool
    destinations: list[CommuteDestination]
    worst_commute_min: float | None = None


def _resolve_station(name: str, stations: list[MrtStation]) -> MrtStation | None:
    needle = name.strip().casefold()
    if not needle:
        return None

    for station in stations:
        if station.station_name.casefold() == needle:
            return station

    for station in stations:
        if needle in station.station_name.casefold() or station.station_name.casefold() in needle:
            return station

    return None


class CommuteTool(ToolAdapter):
    spec = ToolSpec(
        name="commute",
        description="Estimate public-transport commute minutes from a block to stated workplaces.",
        use_case=(
            "Use when the buyer states workplace locations. Returns honest unavailable output "
            "when workplaces or station matches are missing."
        ),
        output_type=CommuteOutput,
        activating_prefs=[PrefDimension(
            field="work_locations",
            prompt="Where do you (and your partner) work? - unlocks commute analysis",
            question="Where do you (and your partner) work? — unlocks commute-time analysis",
            default=[],
        )],
    )

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return mock_commute_data(block_id or 0, prefs)

        workplaces = prefs.get("work_locations") or []
        if not workplaces or block_id is None:
            return {"available": False, "destinations": [], "worst_commute_min": None}

        block = repo.block(block_id)
        if block is None:
            return {"available": False, "destinations": [], "worst_commute_min": None}

        stations = list(repo.mrt_stations(status="operational"))
        provider = HeuristicCommuteProvider(stations)
        destinations: list[dict[str, Any]] = []
        resolved_minutes: list[float] = []

        for workplace in workplaces:
            station = _resolve_station(str(workplace), stations)
            if station is None:
                destinations.append({
                    "name": str(workplace),
                    "resolved": False,
                    "travel_min": None,
                    "transfers": None,
                    "mode": None,
                })
                continue

            route = provider.route(block.point, station.point, mode="pt")
            destinations.append({
                "name": station.station_name,
                "resolved": True,
                "travel_min": route.total_minutes,
                "transfers": route.transfers,
                "mode": route.mode,
            })
            resolved_minutes.append(route.total_minutes)

        worst = max(resolved_minutes) if resolved_minutes else None
        return {"available": bool(resolved_minutes), "destinations": destinations, "worst_commute_min": worst}

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_commute() -> dict[str, Any]:
            """Estimate transit commute from the current block to the buyer's workplaces."""
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=_prefs)

        return get_commute
