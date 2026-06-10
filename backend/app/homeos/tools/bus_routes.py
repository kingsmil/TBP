from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from app.homeos.framework.spec import PrefDimension, ToolSpec
from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_bus_routes_data

if TYPE_CHECKING:
    from app.repositories.base import Repository

_UNAVAILABLE: dict[str, Any] = {"available": False, "nearest_stop": None, "services": []}


class NearestBusStop(BaseModel):
    model_config = {"extra": "ignore"}
    code: str
    distance_m: float | None = None


class BusService(BaseModel):
    model_config = {"extra": "ignore"}
    service_no: str
    stops_reachable: int


class BusRoutesOutput(BaseModel):
    model_config = {"extra": "ignore"}
    available: bool
    nearest_stop: NearestBusStop | None = None
    services: list[BusService] = Field(default_factory=list)


class BusRoutesTool(ToolAdapter):
    spec = ToolSpec(
        name="bus_routes",
        description="Bus services reachable from the block's nearest stops.",
        use_case=(
            "Call when the buyer is bus-dependent (no car); evaluates last-mile "
            "coverage beyond raw stop counts."
        ),
        output_type=BusRoutesOutput,
        activating_prefs=[PrefDimension(
            field="bus_reliance",
            prompt="Do you rely on buses / no car? - unlocks bus network analysis",
            question="Do you rely on buses, or do you have a car? — unlocks bus network analysis",
            default="low",
        )],
    )

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return mock_bus_routes_data(block_id or 0)

        prox = repo.proximity(block_id) if block_id is not None else None
        if prox is None or prox.nearest_bus_stop_code is None:
            return dict(_UNAVAILABLE)

        nearest_stop = {
            "code": prox.nearest_bus_stop_code,
            "distance_m": prox.nearest_bus_distance_m,
        }
        reach = repo.bus_stop_reach(prox.nearest_bus_stop_code)
        if not reach or not reach.get("services"):
            return {**_UNAVAILABLE, "nearest_stop": nearest_stop}

        best_reach: dict[str, int] = {}
        for service in reach["services"]:
            downstream = max(len(service.get("stops", [])) - 1, 0)
            service_no = service["service_no"]
            best_reach[service_no] = max(best_reach.get(service_no, 0), downstream)

        services = [
            {"service_no": service_no, "stops_reachable": count}
            for service_no, count in sorted(best_reach.items())
        ]
        return {"available": True, "nearest_stop": nearest_stop, "services": services}

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_bus_routes() -> dict[str, Any]:
            """List bus services reachable from the current block's nearest stop."""
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=_prefs)

        return get_bus_routes
