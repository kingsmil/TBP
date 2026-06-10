from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_proximity_data

if TYPE_CHECKING:
    from app.repositories.base import Repository


class ProximityTool(ToolAdapter):
    name = "proximity"
    description = "Fetch MRT distance and school count for a block."

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return mock_proximity_data(block_id or 0)
        prox = repo.proximity(block_id)
        if prox is None:
            return {"connections": []}
        mrt_dist = prox.nearest_mrt_distance_m
        mrt_signal = (
            "strong" if mrt_dist is not None and mrt_dist <= 500
            else "moderate" if mrt_dist is not None and mrt_dist <= 1000
            else "weak"
        )
        school_count = prox.schools_within_1km
        school_signal = "strong" if school_count >= 2 else "moderate" if school_count == 1 else "weak"
        return {
            "connections": [
                {"type": "mrt", "name": "Nearest operational MRT", "distance_m": mrt_dist, "signal": mrt_signal},
                {"type": "primary_school", "name": "Primary schools within 1km", "count": school_count, "signal": school_signal},
            ]
        }

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_proximity() -> dict[str, Any]:
            """Fetch MRT distance and school proximity for the current block."""
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=_prefs)

        return get_proximity
