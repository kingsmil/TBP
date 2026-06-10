from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from app.homeos.framework.spec import ToolSpec
from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_search_data

if TYPE_CHECKING:
    from app.repositories.base import Repository


class BlockSummary(BaseModel):
    model_config = {"extra": "ignore"}
    block_id: int
    block_number: str
    street_name: str
    town: str
    lon: float = 0.0
    lat: float = 0.0
    lease_commencement_year: int | None = None
    nearest_mrt_distance_m: float | None = None
    schools_within_1km: int | None = None
    median_psf: float | None = None
    median_price: float | None = None
    txn_count: int | None = None


class SearchOutput(BaseModel):
    model_config = {"extra": "ignore"}
    results: list[BlockSummary]


class SearchTool(ToolAdapter):
    spec = ToolSpec(
        name="search",
        description="Search and filter HDB blocks by flat type, max price, town, MRT distance, and school count.",
        use_case=(
            "Use during the search phase to find candidate blocks matching buyer preferences. "
            "Do not call during per-block deep analysis — use block-specific tools instead."
        ),
        output_type=SearchOutput,
    )

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return {"results": mock_search_data(prefs, 100)}
        from app.core.models import SearchQuery
        from app.services.search import search_blocks
        q = SearchQuery(
            flat_type=prefs.get("flat_type"),
            max_price=prefs.get("max_price"),
            town=prefs.get("town"),
            min_schools_within_1km=prefs.get("min_schools_within_1km"),
            limit=100,
        )
        return {"results": search_blocks(repo, q)}

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _prefs = repo, prefs

        def search_blocks_tool(
            flat_type: str | None = None,
            max_price: float | None = None,
            town: str | None = None,
        ) -> dict[str, Any]:
            """Search HDB blocks. Override flat_type, max_price, or town from buyer preferences."""
            p = {
                **_prefs,
                **({"flat_type": flat_type} if flat_type else {}),
                **({"max_price": max_price} if max_price else {}),
                **({"town": town} if town else {}),
            }
            return _self.fetch(repo=_repo, block_id=None, prefs=p)

        return search_blocks_tool
