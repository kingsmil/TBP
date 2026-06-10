from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_accessibility_data

if TYPE_CHECKING:
    from app.repositories.base import Repository


class AccessibilityTool(ToolAdapter):
    name = "accessibility"
    description = "Fetch bus stop accessibility data for a block."

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
