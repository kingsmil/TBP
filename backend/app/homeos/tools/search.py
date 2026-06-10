from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from app.core.models import HDBTown
from app.homeos.framework.spec import PrefDimension, ToolSpec
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


def _fuzzy_match_town(town_input: str) -> HDBTown | None:
    """Fuzzy match town input to HDBTown enum.

    Handles partial matches, common abbreviations, and variations.
    """
    if not town_input:
        return None

    town_upper = town_input.upper().strip()

    # Ignore very short inputs (likely not town names)
    if len(town_upper) < 3:
        return None

    # Direct match first
    try:
        return HDBTown(town_upper)
    except ValueError:
        pass

    # Exact match by enum value
    for town in HDBTown:
        if town.value == town_upper:
            return town

    # Common abbreviations and variations (check before partial matching)
    abbreviations = {
        "CENTRAL": HDBTown.CENTRAL_AREA,
        "CBD": HDBTown.CENTRAL_AREA,
        "DOWNTOWN": HDBTown.CENTRAL_AREA,
        "CITY": HDBTown.CENTRAL_AREA,
        "AMK": HDBTown.ANG_MO_KIO,
        "CCK": HDBTown.CHOA_CHU_KANG,
        "JE": HDBTown.JURONG_EAST,
        "JW": HDBTown.JURONG_WEST,
        "JUR": HDBTown.JURONG_WEST,  # Default "jurong" to west
        "TPY": HDBTown.TOA_PAYOH,
        "KALLANG": HDBTown.KALLANG_WHAMPOA,
        "WHAMPOA": HDBTown.KALLANG_WHAMPOA,
    }

    if town_upper in abbreviations:
        return abbreviations[town_upper]

    # Word-based exact matching (all words must match completely)
    input_words = town_upper.split()
    if input_words:
        for town in HDBTown:
            town_words = town.value.split()
            if all(word in town_words for word in input_words):
                return town

    # Partial match - check if input starts a town name (more restrictive)
    for town in HDBTown:
        if town.value.startswith(town_upper):
            return town

    return None


class SearchTool(ToolAdapter):
    spec = ToolSpec(
        name="search",
        description="Search and filter HDB blocks by flat type, max price, town, MRT distance, and school count.",
        use_case=(
            "Use during the search phase to find candidate blocks matching buyer preferences. "
            "Do not call during per-block deep analysis — use block-specific tools instead."
        ),
        output_type=SearchOutput,
        activating_prefs=[
            PrefDimension(field="flat_type",
                          prompt="Flat type (2/3/4/5-room or Executive)",
                          query_key="flat_type"),
            PrefDimension(field="max_price",
                          prompt="Your budget ceiling — drives the budget-fit verdict",
                          query_key="max_price"),
            PrefDimension(field="town",
                          prompt="A preferred town or estate (optional)",
                          query_key="town"),
        ],
    )

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return {"results": mock_search_data(prefs, 100)}
        from app.core.models import SearchQuery
        from app.services.search import search_blocks

        # Convert commute_priority to max_mrt_distance_m
        max_mrt_distance_m = None
        commute_priority = prefs.get("commute_priority", "low")
        if commute_priority == "high":
            max_mrt_distance_m = 600.0
        elif commute_priority == "medium":
            max_mrt_distance_m = 1200.0

        q = SearchQuery(
            flat_type=prefs.get("flat_type"),
            max_price=prefs.get("max_price"),
            town=prefs.get("town"),
            min_schools_within_1km=prefs.get("min_schools_within_1km"),
            max_mrt_distance_m=max_mrt_distance_m,
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
            """Search HDB blocks. Override flat_type, max_price, or town from buyer preferences.

            Args:
                flat_type: One of "2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE"
                max_price: Maximum price in SGD
                town: HDB town name. Valid towns:
                    - ANG MO KIO, BEDOK, BISHAN, BUKIT BATOK, BUKIT MERAH
                    - BUKIT PANJANG, BUKIT TIMAH, CENTRAL AREA, CHOA CHU KANG
                    - CLEMENTI, GEYLANG, HOUGANG, JURONG EAST, JURONG WEST
                    - KALLANG/WHAMPOA, MARINE PARADE, PASIR RIS, PUNGGOL
                    - QUEENSTOWN, SEMBAWANG, SENGKANG, SERANGOON, TAMPINES
                    - TOA PAYOH, WOODLANDS, YISHUN

                    Note: Use "CENTRAL AREA" not "CENTRAL", "KALLANG/WHAMPOA" not "KALLANG"
                    Partial matches work: "BUKIT" will match first BUKIT town
            """
            # Convert town string to HDBTown enum with fuzzy matching
            town_enum = _fuzzy_match_town(town) if town else None

            p = {
                **_prefs,
                **({"flat_type": flat_type} if flat_type else {}),
                **({"max_price": max_price} if max_price else {}),
                **({"town": town_enum} if town_enum else {}),
            }
            return _self.fetch(repo=_repo, block_id=None, prefs=p)

        return search_blocks_tool
