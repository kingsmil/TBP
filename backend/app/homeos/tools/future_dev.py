from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_future_dev_data

if TYPE_CHECKING:
    from app.repositories.base import Repository


class FutureDevTool(ToolAdapter):
    name = "future_dev"
    description = "Fetch future MRT and future supply data for a block."

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
