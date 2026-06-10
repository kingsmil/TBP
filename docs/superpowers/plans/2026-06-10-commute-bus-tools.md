# Commute + Bus Routes Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `commute` and `bus_routes` catalogue tools (Spec 2, `docs/superpowers/specs/2026-06-10-commute-bus-tools-design.md`) so deep analysis reasons about the buyer's workplaces and bus dependence, with honest no-data behaviour.

**Architecture:** Two new `ToolAdapter`s registered in the `ToolRepository` catalogue and wired into the `location` agent. The commute tool resolves workplace names against MRT station names and estimates door-to-door minutes with the existing `HeuristicCommuteProvider`. The bus tool walks `repo.proximity → bus_stop_reach`. A minimal `PrefDimension` dataclass + `activating_prefs` field is included here (pure data, no gate logic) so the tools declare their activating questions now; Spec 1 builds the review gate that consumes them.

**Tech Stack:** Python 3.12, pydantic v2, pydantic-ai (TestModel for offline tests), unittest/pytest, in-memory + PostGIS repositories.

**Working directory:** `<worktree>/backend` where `<worktree>` = `/Users/moethu/Documents/Codex/hack/estate-finder/.claude/worktrees/feat+commute-bus-tools`. Branch: `feat/commute-bus-tools`.

**Test runner:** the worktree has no venv; use the main checkout's interpreter:

```bash
VENV=/Users/moethu/Documents/Codex/hack/estate-finder/backend/.venv/bin/python
# run from <worktree>/backend
$VENV -m pytest tests/ -q
```

**Baseline (verified before this plan):** `250 passed, 3 failed, 16 skipped` — the 3 failures are the known `tests/test_homeos_stream.py` clarifying-question failures on main (Spec 1 fixes them; NOT regressions). Any other failure you introduce is yours.

---

## Approved deviations from the spec (rationale recorded — do not "fix" these back)

1. **Spec 1 is NOT a prerequisite.** This branch ships the tiny `PrefDimension` dataclass and `activating_prefs` fields itself (Task 1). Spec 1's gate (`review_dimensions()`, `_preference_review`) stays out of scope, so the spec's tests asserting "the preference review now lists the two new questions" are deferred to Spec 1.
2. **Commute fetch uses `HeuristicCommuteProvider`, not `repo.direct_transit_convenience`.** The spec's suggested repo method is PostGIS-only and is a block *search* returning walk distances — it cannot produce the spec's own `travel_min` field. `HeuristicCommuteProvider` (`app/services/commute/provider.py`) already models walk→rail→walk minutes from any `Repository` via `mrt_stations()`, works on the in-memory repo, and is the "existing commute capability" the spec's Goal section says to wrap.
3. **The mock dataset generator does NOT already create bus routes** (spec claims it does; it only creates 3 stops/area, `app/data/mock.py:81`). Instead of touching the generator, `InMemoryRepository` gains `add_bus_routes()` + `bus_stop_reach()` (Task 4), and the integration test seeds a few route rows directly.

---

## File map

| File | Change |
|---|---|
| `app/homeos/framework/spec.py` | + `PrefDimension`; + `activating_prefs` on `ToolSpec` & `AgentSpec` |
| `app/homeos/models/avatar.py` | + `work_locations`, `bus_reliance` on `HomeOSPreferences` |
| `app/homeos/agents/profile.py` | prompt extracts the two new prefs |
| `app/homeos/tools/commute.py` | **new** — `CommuteTool`, `CommuteOutput`, `_resolve_station` |
| `app/homeos/tools/bus_routes.py` | **new** — `BusRoutesTool`, `BusRoutesOutput` |
| `app/homeos/mock/tools.py` | + `mock_commute_data`, `mock_bus_routes_data` |
| `app/repositories/base.py` | + abstract `bus_stop_reach` |
| `app/repositories/memory.py` | + `add_bus_routes`, `bus_stop_reach` |
| `app/homeos/wiring.py` | register both tools |
| `app/homeos/agents/location.py` | tool_names/prefetch += commute, bus_routes; prompt guard |
| `app/homeos/pipeline.py` | location_evidence carries `commute` + `bus_routes` keys |
| `app/homeos/scoring.py` | long-commute watchout |
| `tests/test_homeos_commute_bus_tools.py` | **new** — all unit tests |
| `tests/integration/test_tool_adapters.py` | + commute/bus adapter tests |
| `tests/integration/test_agents.py` | + location prefetch-keys test |
| `tests/e2e/test_tools_e2e.py` | + real-DB commute + empty-bus tests |
| `tests/e2e/test_live_llm.py` | rename location test (coverage is automatic) |

---

### Task 1: `PrefDimension` + `activating_prefs` (Spec 1 decoupling shim)

**Files:**
- Modify: `app/homeos/framework/spec.py`
- Test: `tests/test_homeos_commute_bus_tools.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_homeos_commute_bus_tools.py`:

```python
"""Unit tests for Spec 2: commute + bus_routes tools, activating prefs, scoring watchout."""
import unittest

from pydantic import BaseModel

from app.homeos.framework.spec import AgentSpec, PrefDimension, ToolSpec


class _DummyOutput(BaseModel):
    ok: bool = True


class TestPrefDimension(unittest.TestCase):
    def test_pref_dimension_defaults(self):
        dim = PrefDimension(field="work_locations", prompt="Where do you work?")
        self.assertIsNone(dim.query_key)
        self.assertIsNone(dim.default)

    def test_tool_spec_activating_prefs_defaults_empty(self):
        spec = ToolSpec(name="t", description="d", use_case="u", output_type=_DummyOutput)
        self.assertEqual(spec.activating_prefs, [])

    def test_agent_spec_activating_prefs_defaults_empty(self):
        spec = AgentSpec(name="a", description="d", system_prompt="s", output_type=_DummyOutput)
        self.assertEqual(spec.activating_prefs, [])

    def test_activating_prefs_are_per_instance(self):
        a = ToolSpec(name="t1", description="d", use_case="u", output_type=_DummyOutput)
        b = ToolSpec(name="t2", description="d", use_case="u", output_type=_DummyOutput)
        a.activating_prefs.append(PrefDimension(field="x", prompt="p"))
        self.assertEqual(b.activating_prefs, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it — must fail**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py -q`
Expected: `ImportError: cannot import name 'PrefDimension'`

- [ ] **Step 3: Implement**

In `app/homeos/framework/spec.py`, add above `ToolSpec`:

```python
@dataclass
class PrefDimension:
    """A buyer-preference dimension that unlocks a tool/agent. Consumed by the
    Spec 1 preference-review gate; declared here so tools can self-describe."""
    field: str            # key in HomeOSPreferences / prefs dict
    prompt: str           # bullet shown to the buyer
    query_key: str | None = None  # SearchQuery key whose absence == "not stated"
    default: str | None = None    # for non-search dims: value meaning "never stated"
```

Add to `ToolSpec` (after `output_type`, before `__post_init__`):

```python
    activating_prefs: list[PrefDimension] = field(default_factory=list)
```

Add the same line to `AgentSpec` (after `prefetch`).

- [ ] **Step 4: Run tests**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/homeos/framework/spec.py tests/test_homeos_commute_bus_tools.py
git commit -m "feat(homeos): add PrefDimension + activating_prefs to ToolSpec/AgentSpec"
```

---

### Task 2: New buyer preferences + profile prompt

**Files:**
- Modify: `app/homeos/models/avatar.py`, `app/homeos/agents/profile.py`
- Test: `tests/test_homeos_commute_bus_tools.py`

- [ ] **Step 1: Write the failing test** (append to the new test file)

```python
from app.homeos.models.avatar import HomeOSPreferences


class TestNewPreferences(unittest.TestCase):
    def test_defaults(self):
        prefs = HomeOSPreferences()
        self.assertEqual(prefs.work_locations, [])
        self.assertEqual(prefs.bus_reliance, "low")

    def test_work_locations_not_shared_between_instances(self):
        a, b = HomeOSPreferences(), HomeOSPreferences()
        a.work_locations.append("Raffles Place")
        self.assertEqual(b.work_locations, [])

    def test_bus_reliance_accepts_high(self):
        self.assertEqual(HomeOSPreferences(bus_reliance="high").bus_reliance, "high")
```

- [ ] **Step 2: Run it — must fail**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py -q`
Expected: `AttributeError: ... work_locations` (FAIL on test_defaults).

- [ ] **Step 3: Implement**

In `app/homeos/models/avatar.py`, add to `HomeOSPreferences` after `appreciation_priority`:

```python
    work_locations: list[str] = Field(default_factory=list)
    bus_reliance: Literal["low", "high"] = "low"
```

In `app/homeos/agents/profile.py`, inside the system prompt, after the `school_priority` line (`"school_priority (high if schools are important). "`), insert:

```python
        "work_locations (list of workplace names exactly as stated, e.g. "
        "['Raffles Place', 'Jurong East'], when the buyer mentions where they work), "
        "bus_reliance: set 'high' if the buyer says they have no car or depend on buses, "
        "else 'low' (default 'low'). "
```

- [ ] **Step 4: Run tests**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py tests/test_homeos_service.py -q`
Expected: all pass (avatar model is exercised broadly; service tests guard regressions).

- [ ] **Step 5: Commit**

```bash
git add app/homeos/models/avatar.py app/homeos/agents/profile.py tests/test_homeos_commute_bus_tools.py
git commit -m "feat(homeos): work_locations + bus_reliance buyer preferences"
```

---

### Task 3: `commute` tool

**Files:**
- Create: `app/homeos/tools/commute.py`
- Modify: `app/homeos/mock/tools.py`
- Test: `tests/test_homeos_commute_bus_tools.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
from app.core.geo import Point
from app.core.models import Block, BlockProximity, BusStop, MrtStation
from app.repositories.memory import InMemoryRepository


def _commute_repo() -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.add_mrt_stations([
        MrtStation(1, "Raffles Place", "EW", "operational", 2010, Point(103.851, 1.284)),
        MrtStation(2, "Jurong East", "EW", "operational", 2010, Point(103.742, 1.333)),
        MrtStation(3, "Tampines East", "DT", "operational", 2017, Point(103.955, 1.356)),
    ])
    repo.add_blocks([Block(
        block_id=1, block_number="101", street_name="TEST ST", postal_code="460101",
        town="BEDOK", planning_area_id=1, lease_commencement_year=2000,
        point=Point(103.93, 1.32),
    )])
    return repo


class TestResolveStation(unittest.TestCase):
    def setUp(self):
        self.stations = list(_commute_repo().mrt_stations())

    def test_exact_match_case_insensitive(self):
        from app.homeos.tools.commute import _resolve_station
        self.assertEqual(_resolve_station("raffles place", self.stations).station_id, 1)

    def test_substring_match(self):
        from app.homeos.tools.commute import _resolve_station
        self.assertEqual(_resolve_station("Tampines", self.stations).station_id, 3)

    def test_unresolved_returns_none(self):
        from app.homeos.tools.commute import _resolve_station
        self.assertIsNone(_resolve_station("Atlantis", self.stations))


class TestCommuteTool(unittest.TestCase):
    def setUp(self):
        self.repo = _commute_repo()

    def _fetch(self, prefs):
        from app.homeos.tools.commute import CommuteTool
        return CommuteTool().fetch(self.repo, 1, prefs)

    def test_empty_work_locations_is_unavailable(self):
        result = self._fetch({"max_price": 700_000})
        self.assertEqual(result, {"available": False, "destinations": [], "worst_commute_min": None})

    def test_resolved_and_unresolved_mix(self):
        from app.homeos.tools.commute import CommuteOutput
        result = self._fetch({"work_locations": ["Raffles Place", "Atlantis"]})
        output = CommuteOutput.model_validate(result)
        self.assertTrue(output.available)
        by_name = {d.name: d for d in output.destinations}
        self.assertTrue(by_name["Raffles Place"].resolved)
        self.assertGreater(by_name["Raffles Place"].travel_min, 0)
        self.assertFalse(by_name["Atlantis"].resolved)
        self.assertIsNone(by_name["Atlantis"].travel_min)
        self.assertEqual(output.worst_commute_min, by_name["Raffles Place"].travel_min)

    def test_worst_commute_is_max(self):
        result = self._fetch({"work_locations": ["Raffles Place", "Jurong East"]})
        mins = [d["travel_min"] for d in result["destinations"]]
        self.assertEqual(result["worst_commute_min"], max(mins))

    def test_all_unresolved_is_unavailable_but_reported(self):
        result = self._fetch({"work_locations": ["Atlantis"]})
        self.assertFalse(result["available"])
        self.assertEqual(result["destinations"][0]["name"], "Atlantis")

    def test_spec_declares_activating_pref(self):
        from app.homeos.tools.commute import CommuteTool
        prefs = CommuteTool.spec.activating_prefs
        self.assertEqual(len(prefs), 1)
        self.assertEqual(prefs[0].field, "work_locations")

    def test_mock_mode_mirrors_shape(self):
        from app.homeos.tools.commute import CommuteOutput, CommuteTool
        tool = CommuteTool(mock=True)
        out = CommuteOutput.model_validate(
            tool.fetch(self.repo, 1, {"work_locations": ["Raffles Place"]}))
        self.assertTrue(out.available)
        empty = CommuteOutput.model_validate(tool.fetch(self.repo, 1, {}))
        self.assertFalse(empty.available)
```

- [ ] **Step 2: Run — must fail**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py -q`
Expected: `ModuleNotFoundError: No module named 'app.homeos.tools.commute'`

- [ ] **Step 3: Add mocks to `app/homeos/mock/tools.py`** (append)

```python
def mock_commute_data(block_id: int, prefs: dict) -> dict[str, Any]:
    locations = prefs.get("work_locations") or []
    if not locations:
        return {"available": False, "destinations": [], "worst_commute_min": None}
    destinations = [
        {"name": name, "resolved": True, "travel_min": 35.0, "mode": "pt"}
        for name in locations
    ]
    return {"available": True, "destinations": destinations, "worst_commute_min": 35.0}


def mock_bus_routes_data(block_id: int) -> dict[str, Any]:
    return {
        "available": True,
        "nearest_stop": {"code": "01001", "distance_m": 150.0},
        "services": [
            {"service_no": "12", "stops_reachable": 18},
            {"service_no": "63", "stops_reachable": 9},
        ],
    }
```

- [ ] **Step 4: Create `app/homeos/tools/commute.py`**

```python
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from app.homeos.framework.spec import PrefDimension, ToolSpec
from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_commute_data
from app.services.commute.provider import HeuristicCommuteProvider

if TYPE_CHECKING:
    from app.core.models import MrtStation
    from app.repositories.base import Repository

_UNAVAILABLE: dict[str, Any] = {
    "available": False, "destinations": [], "worst_commute_min": None,
}


def _resolve_station(name: str, stations: Sequence["MrtStation"]) -> "MrtStation | None":
    """Case-insensitive exact match on station_name, then substring; never guesses."""
    query = name.strip().casefold()
    if not query:
        return None
    exact = [s for s in stations if s.station_name.casefold() == query]
    if exact:
        return min(exact, key=lambda s: s.station_id)
    partial = [s for s in stations if query in s.station_name.casefold()]
    if partial:
        return min(partial, key=lambda s: (len(s.station_name), s.station_id))
    return None


class CommuteDestination(BaseModel):
    model_config = {"extra": "ignore"}
    name: str
    resolved: bool
    travel_min: float | None = None
    mode: str | None = None


class CommuteOutput(BaseModel):
    model_config = {"extra": "ignore"}
    available: bool
    destinations: list[CommuteDestination] = []
    worst_commute_min: float | None = None


class CommuteTool(ToolAdapter):
    spec = ToolSpec(
        name="commute",
        description="Transit convenience from a block to the buyer's workplaces.",
        use_case=(
            "Call when the buyer has stated work locations; assesses realistic "
            "door-to-door transit viability to each workplace."
        ),
        output_type=CommuteOutput,
        activating_prefs=[PrefDimension(
            field="work_locations",
            prompt="Where do you (and your partner) work? — unlocks commute analysis",
        )],
    )

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return mock_commute_data(block_id or 0, prefs)
        work_locations = prefs.get("work_locations") or []
        if not work_locations:
            return dict(_UNAVAILABLE)
        block = repo.block(block_id) if block_id is not None else None
        if block is None:
            return dict(_UNAVAILABLE)
        stations = list(repo.mrt_stations())
        provider = HeuristicCommuteProvider(stations)
        destinations: list[dict[str, Any]] = []
        worst: float | None = None
        for name in work_locations:
            station = _resolve_station(name, stations)
            if station is None:
                destinations.append(
                    {"name": name, "resolved": False, "travel_min": None, "mode": None})
                continue
            route = provider.route(block.point, station.point, mode="pt")
            destinations.append({
                "name": name, "resolved": True,
                "travel_min": route.total_minutes, "mode": route.mode,
            })
            worst = route.total_minutes if worst is None else max(worst, route.total_minutes)
        return {
            "available": any(d["resolved"] for d in destinations),
            "destinations": destinations,
            "worst_commute_min": worst,
        }

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_commute() -> dict[str, Any]:
            """Estimate transit commute from the current block to the buyer's workplaces."""
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=_prefs)

        return get_commute
```

- [ ] **Step 5: Run tests**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/homeos/tools/commute.py app/homeos/mock/tools.py tests/test_homeos_commute_bus_tools.py
git commit -m "feat(homeos): commute tool — workplace resolution + heuristic transit minutes"
```

---

### Task 4: `bus_stop_reach` on the repository interface + in-memory impl

**Files:**
- Modify: `app/repositories/base.py`, `app/repositories/memory.py`
- Test: `tests/test_homeos_commute_bus_tools.py`

The PostGIS repo already implements `bus_stop_reach` (`app/repositories/postgis.py:346`); promoting it to the ABC and adding the in-memory twin lets the bus tool depend on the interface only. `add_bus_routes` is an in-memory-only loader (PostGIS routes are written by `app/data/sync_bus_network.py` SQL — do NOT add it to the ABC, it would break `PostgisRepository` instantiation).

- [ ] **Step 1: Write the failing tests** (append)

```python
class TestInMemoryBusStopReach(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryRepository()
        self.repo.add_bus_stops([
            BusStop("01001", "Stop A", Point(103.93, 1.32)),
            BusStop("01002", "Stop B", Point(103.94, 1.32)),
            BusStop("01003", "Stop C", Point(103.95, 1.33)),
        ])
        self.repo.add_bus_routes([
            {"service_no": "12", "direction": 1, "stop_sequence": 1, "bus_stop_code": "01001"},
            {"service_no": "12", "direction": 1, "stop_sequence": 2, "bus_stop_code": "01002"},
            {"service_no": "12", "direction": 1, "stop_sequence": 3, "bus_stop_code": "01003"},
            {"service_no": "63", "direction": 1, "stop_sequence": 5, "bus_stop_code": "01002"},
            {"service_no": "63", "direction": 1, "stop_sequence": 6, "bus_stop_code": "01001"},
        ])

    def test_unknown_stop_returns_none(self):
        self.assertIsNone(self.repo.bus_stop_reach("99999"))

    def test_reach_shape_matches_postgis(self):
        reach = self.repo.bus_stop_reach("01001")
        self.assertEqual(reach["origin"]["bus_stop_code"], "01001")
        self.assertEqual(reach["service_count"], 2)
        by_no = {s["service_no"]: s for s in reach["services"]}
        # service 12 boards at seq 1 and reaches B and C downstream
        self.assertEqual([s["bus_stop_code"] for s in by_no["12"]["stops"]],
                         ["01001", "01002", "01003"])
        # service 63 boards 01001 at seq 6 — nothing downstream
        self.assertEqual([s["bus_stop_code"] for s in by_no["63"]["stops"]], ["01001"])
        self.assertEqual(reach["reachable_stop_count"], 2)

    def test_stop_with_no_routes_returns_empty_services(self):
        repo = InMemoryRepository()
        repo.add_bus_stops([BusStop("02001", "Lonely", Point(103.9, 1.3))])
        reach = repo.bus_stop_reach("02001")
        self.assertEqual(reach["services"], [])
        self.assertEqual(reach["service_count"], 0)
```

- [ ] **Step 2: Run — must fail**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py -q`
Expected: `AttributeError: 'InMemoryRepository' object has no attribute 'add_bus_routes'`

- [ ] **Step 3: Implement**

`app/repositories/base.py` — add after the `proximity` abstractmethod:

```python
    @abstractmethod
    def bus_stop_reach(self, bus_stop_code: str) -> dict | None:
        """Services boarding at this stop and every stop reachable downstream."""
```

`app/repositories/memory.py` — in `__init__`, add:

```python
        self._bus_routes: list[dict] = []
```

Add after `set_proximity` (loader section):

```python
    def add_bus_routes(self, items: Iterable[dict]) -> None:
        """Route rows: {service_no, direction, stop_sequence, bus_stop_code}.
        In-memory only — PostGIS routes are ingested by sync_bus_network.py."""
        self._bus_routes.extend(items)
```

Add after `proximity` (reads section), mirroring the PostGIS return shape:

```python
    def bus_stop_reach(self, bus_stop_code: str) -> dict | None:
        origin = self._bus.get(bus_stop_code)
        if origin is None:
            return None
        boardings: dict[tuple[str, int], int] = {}
        for r in self._bus_routes:
            if r["bus_stop_code"] == bus_stop_code:
                key = (r["service_no"], r["direction"])
                boardings[key] = min(boardings.get(key, r["stop_sequence"]), r["stop_sequence"])
        services: list[dict] = []
        reachable: dict[str, dict] = {}
        for (service_no, direction), seq in sorted(boardings.items()):
            downstream = sorted(
                (r for r in self._bus_routes
                 if r["service_no"] == service_no and r["direction"] == direction
                 and r["stop_sequence"] >= seq),
                key=lambda r: r["stop_sequence"])
            stops = []
            for r in downstream:
                stop_entity = self._bus.get(r["bus_stop_code"])
                if stop_entity is None:
                    continue
                stop = {
                    "bus_stop_code": stop_entity.bus_stop_code,
                    "description": stop_entity.description,
                    "lat": stop_entity.point.lat,
                    "lon": stop_entity.point.lon,
                    "stop_sequence": r["stop_sequence"],
                }
                stops.append(stop)
                if stop_entity.bus_stop_code != bus_stop_code:
                    reachable[stop_entity.bus_stop_code] = stop
            services.append({"service_no": service_no, "direction": direction, "stops": stops})
        return {
            "origin": {
                "bus_stop_code": origin.bus_stop_code,
                "description": origin.description,
                "lat": origin.point.lat,
                "lon": origin.point.lon,
            },
            "service_count": len(services),
            "reachable_stop_count": len(reachable),
            "services": services,
            "reachable_stops": list(reachable.values()),
        }
```

- [ ] **Step 4: Run the full unit suite** (the new abstractmethod must not break anything)

Run: `$VENV -m pytest tests/ -q --ignore=tests/e2e`
Expected: only the 3 known `test_homeos_stream` baseline failures.

- [ ] **Step 5: Commit**

```bash
git add app/repositories/base.py app/repositories/memory.py tests/test_homeos_commute_bus_tools.py
git commit -m "feat(repo): bus_stop_reach on Repository interface + in-memory implementation"
```

---

### Task 5: `bus_routes` tool

**Files:**
- Create: `app/homeos/tools/bus_routes.py`
- Test: `tests/test_homeos_commute_bus_tools.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
def _bus_repo(with_routes: bool = True) -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.add_bus_stops([
        BusStop("01001", "Stop A", Point(103.93, 1.32)),
        BusStop("01002", "Stop B", Point(103.94, 1.32)),
    ])
    repo.set_proximity([BlockProximity(
        block_id=1, nearest_bus_stop_code="01001", nearest_bus_distance_m=150.0)])
    if with_routes:
        repo.add_bus_routes([
            {"service_no": "12", "direction": 1, "stop_sequence": 1, "bus_stop_code": "01001"},
            {"service_no": "12", "direction": 1, "stop_sequence": 2, "bus_stop_code": "01002"},
            {"service_no": "12", "direction": 2, "stop_sequence": 9, "bus_stop_code": "01001"},
        ])
    return repo


class TestBusRoutesTool(unittest.TestCase):
    def _fetch(self, repo, block_id=1):
        from app.homeos.tools.bus_routes import BusRoutesTool
        return BusRoutesTool().fetch(repo, block_id, {})

    def test_no_proximity_row_is_unavailable(self):
        result = self._fetch(InMemoryRepository(), block_id=42)
        self.assertEqual(result, {"available": False, "nearest_stop": None, "services": []})

    def test_empty_routes_is_unavailable_but_keeps_nearest_stop(self):
        result = self._fetch(_bus_repo(with_routes=False))
        self.assertFalse(result["available"])
        self.assertEqual(result["nearest_stop"], {"code": "01001", "distance_m": 150.0})
        self.assertEqual(result["services"], [])

    def test_services_aggregated_by_service_no(self):
        from app.homeos.tools.bus_routes import BusRoutesOutput
        result = self._fetch(_bus_repo())
        output = BusRoutesOutput.model_validate(result)
        self.assertTrue(output.available)
        self.assertEqual(len(output.services), 1)  # directions collapsed
        self.assertEqual(output.services[0].service_no, "12")
        self.assertEqual(output.services[0].stops_reachable, 1)  # best direction reaches Stop B

    def test_spec_declares_activating_pref_with_default(self):
        from app.homeos.tools.bus_routes import BusRoutesTool
        prefs = BusRoutesTool.spec.activating_prefs
        self.assertEqual(prefs[0].field, "bus_reliance")
        self.assertEqual(prefs[0].default, "low")

    def test_mock_mode_validates(self):
        from app.homeos.tools.bus_routes import BusRoutesOutput, BusRoutesTool
        out = BusRoutesOutput.model_validate(
            BusRoutesTool(mock=True).fetch(InMemoryRepository(), 1, {}))
        self.assertTrue(out.available)
```

- [ ] **Step 2: Run — must fail**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py -q`
Expected: `ModuleNotFoundError: No module named 'app.homeos.tools.bus_routes'`

- [ ] **Step 3: Create `app/homeos/tools/bus_routes.py`**

```python
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

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
    services: list[BusService] = []


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
            prompt="Do you rely on buses / no car? — unlocks bus network analysis",
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
            no = service["service_no"]
            best_reach[no] = max(best_reach.get(no, 0), downstream)
        services = [
            {"service_no": no, "stops_reachable": count}
            for no, count in sorted(best_reach.items())
        ]
        return {"available": True, "nearest_stop": nearest_stop, "services": services}

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_bus_routes() -> dict[str, Any]:
            """List bus services reachable from the current block's nearest stop."""
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=_prefs)

        return get_bus_routes
```

- [ ] **Step 4: Run tests**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/homeos/tools/bus_routes.py tests/test_homeos_commute_bus_tools.py
git commit -m "feat(homeos): bus_routes tool — nearest-stop service reach with honest empty-data path"
```

---

### Task 6: Wiring + location agent

**Files:**
- Modify: `app/homeos/wiring.py`, `app/homeos/agents/location.py`
- Test: `tests/integration/test_agents.py`

- [ ] **Step 1: Write the failing test** — append to `tests/integration/test_agents.py` inside `TestAgentsIntegration`:

```python
    def test_location_agent_prefetches_commute_and_bus_routes(self):
        spec = self.tr.get_agent("location")
        self.assertEqual(set(spec.tool_names), {"proximity", "commute", "bus_routes"})
        self.assertEqual(set(spec.prefetch), {"proximity", "commute", "bus_routes"})
        _, prefetched = self.tr.build_agent(
            "location", self.repo, self.block_id, self.prefs)
        self.assertEqual(set(prefetched), {"proximity", "commute", "bus_routes"})
        # no work_locations in prefs → commute must be honestly unavailable
        self.assertFalse(prefetched["commute"]["available"])
```

- [ ] **Step 2: Run — must fail**

Run: `$VENV -m pytest tests/integration/test_agents.py -q`
Expected: FAIL — `{'proximity'} != {'proximity', 'commute', 'bus_routes'}`

- [ ] **Step 3: Implement**

`app/homeos/wiring.py` — extend the imports and the registration tuple:

```python
    from app.homeos.tools.transactions import TransactionsTool
    from app.homeos.tools.proximity import ProximityTool
    from app.homeos.tools.appreciation import AppreciationTool
    from app.homeos.tools.future_dev import FutureDevTool
    from app.homeos.tools.accessibility import AccessibilityTool
    from app.homeos.tools.search import SearchTool
    from app.homeos.tools.commute import CommuteTool
    from app.homeos.tools.bus_routes import BusRoutesTool

    tool_repository = ToolRepository(mock=mock)
    for cls in (TransactionsTool, ProximityTool, AppreciationTool,
                FutureDevTool, AccessibilityTool, SearchTool,
                CommuteTool, BusRoutesTool):
        tool_repository.register_tool(cls(mock=mock))
```

`app/homeos/agents/location.py` — replace the whole definition:

```python
location_definition = AgentSpec(
    name="location",
    description="Evaluates MRT distance and school proximity to score location suitability for a buyer.",
    system_prompt=(
        "You are an HDB location analyst. "
        "Given MRT distance and school proximity data (in pre-fetched context), "
        "summarise the location evidence. "
        "Commute and bus-route data may also be pre-fetched: include those findings "
        "in the narrative ONLY when that section has available: true; when "
        "available is false, ignore the section entirely and never invent coverage. "
        "Write a one-sentence narrative (max 30 words) describing the connectivity for this buyer. "
        "Copy the connections list directly from pre-fetched context."
    ),
    output_type=LocationEvidence,
    tool_names=["proximity", "commute", "bus_routes"],
    prefetch=["proximity", "commute", "bus_routes"],
)
```

- [ ] **Step 4: Run tests**

Run: `$VENV -m pytest tests/integration/ tests/test_tool_repository.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/homeos/wiring.py app/homeos/agents/location.py tests/integration/test_agents.py
git commit -m "feat(homeos): register commute + bus_routes tools and wire into location agent"
```

---

### Task 7: Pipeline evidence merge

**Files:**
- Modify: `app/homeos/pipeline.py` (location section of `_deep_analysis_stream`, around line 186-197)
- Test: `tests/integration/test_agents.py`

- [ ] **Step 1: Write the failing test** — append to `tests/integration/test_agents.py`:

```python
    def test_location_evidence_dict_carries_commute_and_bus_keys(self):
        # Mirrors the pipeline's location_evidence assembly without streaming.
        _, prefetched = self.tr.build_agent(
            "location", self.repo, self.block_id,
            {**self.prefs, "work_locations": ["MRT-1"]})
        evidence = {
            **prefetched.get("proximity", {}),
            "commute": prefetched.get("commute", {}),
            "bus_routes": prefetched.get("bus_routes", {}),
            "narrative": "",
        }
        self.assertIn("connections", evidence)
        self.assertTrue(evidence["commute"]["available"])   # MRT-1 is a seeded station name
        self.assertIn("available", evidence["bus_routes"])
```

- [ ] **Step 2: Run — this passes already (it tests the seeded repo + assembly recipe). Now make the pipeline match it.**

In `app/homeos/pipeline.py` replace (current line ~197):

```python
            location_evidence = {**prox_data, "narrative": location_narrative}
```

with:

```python
            location_evidence = {
                **prox_data,
                "commute": prefetched_loc.get("commute", {}),
                "bus_routes": prefetched_loc.get("bus_routes", {}),
                "narrative": location_narrative,
            }
```

- [ ] **Step 3: Run the suite**

Run: `$VENV -m pytest tests/ -q --ignore=tests/e2e`
Expected: only the 3 known baseline failures.

- [ ] **Step 4: Commit**

```bash
git add app/homeos/pipeline.py tests/integration/test_agents.py
git commit -m "feat(homeos): carry commute + bus_routes evidence through location section"
```

---

### Task 8: Scoring watchout

**Files:**
- Modify: `app/homeos/scoring.py`
- Test: `tests/test_homeos_commute_bus_tools.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
from app.homeos.scoring import worth_viewing_score

_MARKET = {"budget_signal": "within_budget", "transaction_count": 5}
_RISK = {"watchouts": [], "score_adjustment": 0.0}


class TestLongCommuteWatchout(unittest.TestCase):
    def _location(self, worst, available=True):
        return {
            "connections": [],
            "commute": {
                "available": available,
                "destinations": [
                    {"name": "Raffles Place", "resolved": True, "travel_min": worst, "mode": "pt"},
                    {"name": "Jurong East", "resolved": True, "travel_min": 20.0, "mode": "pt"},
                ],
                "worst_commute_min": worst,
            },
        }

    def test_watchout_added_when_worst_over_60(self):
        _, _, watchouts = worth_viewing_score(_MARKET, self._location(75.0), _RISK, {})
        self.assertTrue(any("Long commute to Raffles Place" in w for w in watchouts))

    def test_no_watchout_at_or_under_60(self):
        _, _, watchouts = worth_viewing_score(_MARKET, self._location(60.0), _RISK, {})
        self.assertFalse(any("Long commute" in w for w in watchouts))

    def test_no_watchout_when_unavailable(self):
        _, _, watchouts = worth_viewing_score(
            _MARKET, self._location(75.0, available=False), _RISK, {})
        self.assertFalse(any("Long commute" in w for w in watchouts))

    def test_score_unchanged_by_commute(self):
        base, _, _ = worth_viewing_score(_MARKET, {"connections": []}, _RISK, {})
        scored, _, _ = worth_viewing_score(_MARKET, self._location(75.0), _RISK, {})
        self.assertEqual(base, scored)
```

- [ ] **Step 2: Run — must fail**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py -q`
Expected: FAIL — no "Long commute" watchout.

- [ ] **Step 3: Implement** — in `app/homeos/scoring.py`, after the `for conn in location.get("connections", []):` loop and before `score += risk.get("score_adjustment") or 0.0`:

```python
    commute = location.get("commute") or {}
    worst = commute.get("worst_commute_min")
    if commute.get("available") and worst is not None and worst > 60:
        resolved = [d for d in commute.get("destinations", [])
                    if d.get("resolved") and d.get("travel_min") is not None]
        if resolved:
            worst_dest = max(resolved, key=lambda d: d["travel_min"])
            watchouts.append(f"Long commute to {worst_dest['name']} (~{worst_dest['travel_min']:.0f} min).")
```

(No score-weight change — spec keeps blast radius small.)

- [ ] **Step 4: Run tests**

Run: `$VENV -m pytest tests/test_homeos_commute_bus_tools.py tests/test_homeos_agents_scaffold.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/homeos/scoring.py tests/test_homeos_commute_bus_tools.py
git commit -m "feat(homeos): long-commute watchout in worth_viewing_score"
```

---

### Task 9: Integration tests for the two adapters

**Files:**
- Modify: `tests/integration/test_tool_adapters.py`

- [ ] **Step 1: Append tests** (inside `TestToolAdaptersIntegration`)

```python
    def test_commute_tool_output_validates(self):
        from app.homeos.tools.commute import CommuteTool, CommuteOutput
        tool = CommuteTool()
        result = tool.fetch(self.repo, self.block_id,
                            {**self.prefs, "work_locations": ["MRT-1", "Nowhere Special"]})
        output = CommuteOutput.model_validate(result)
        self.assertTrue(output.available)
        resolved = {d.name: d.resolved for d in output.destinations}
        self.assertTrue(resolved["MRT-1"])
        self.assertFalse(resolved["Nowhere Special"])
        self.assertIsNotNone(output.worst_commute_min)

    def test_commute_tool_without_work_locations_is_unavailable(self):
        from app.homeos.tools.commute import CommuteTool, CommuteOutput
        output = CommuteOutput.model_validate(
            CommuteTool().fetch(self.repo, self.block_id, self.prefs))
        self.assertFalse(output.available)
        self.assertEqual(output.destinations, [])

    def test_bus_routes_tool_with_seeded_routes(self):
        from app.homeos.tools.bus_routes import BusRoutesTool, BusRoutesOutput
        prox = self.repo.proximity(self.block_id)
        code = prox.nearest_bus_stop_code
        self.assertIsNotNone(code)  # seed generator creates 3 stops/area
        self.repo.add_bus_routes([
            {"service_no": "901", "direction": 1, "stop_sequence": 1, "bus_stop_code": code},
            {"service_no": "901", "direction": 1, "stop_sequence": 2,
             "bus_stop_code": next(s.bus_stop_code for s in self.repo.bus_stops()
                                   if s.bus_stop_code != code)},
        ])
        output = BusRoutesOutput.model_validate(
            BusRoutesTool().fetch(self.repo, self.block_id, {}))
        self.assertTrue(output.available)
        self.assertEqual(output.services[0].service_no, "901")
        self.assertGreaterEqual(output.services[0].stops_reachable, 1)

    def test_bus_routes_tool_without_routes_is_honestly_unavailable(self):
        from app.homeos.tools.bus_routes import BusRoutesTool, BusRoutesOutput
        repo, _ = build_seeded_repo(seed=7, blocks_per_area=2, months=3)
        block_id = list(repo.blocks())[0].block_id
        output = BusRoutesOutput.model_validate(BusRoutesTool().fetch(repo, block_id, {}))
        self.assertFalse(output.available)
        self.assertEqual(output.services, [])
```

NOTE: `test_bus_routes_tool_with_seeded_routes` mutates the class-level repo by adding routes; it must use a service number ("901") no other test asserts on, and `test_bus_routes_tool_without_routes_is_honestly_unavailable` builds its own repo so test order cannot matter.

- [ ] **Step 2: Run**

Run: `$VENV -m pytest tests/integration/test_tool_adapters.py -q`
Expected: all pass (if `nearest_bus_stop_code` assertion fails, the seeded proximity rows lack bus codes — inspect `app/data/ingest.py` proximity computation and pick a block whose proximity has a bus code instead of asserting on block[0]).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_tool_adapters.py
git commit -m "test(homeos): integration coverage for commute + bus_routes adapters"
```

---

### Task 10: E2E + live test additions

**Files:**
- Modify: `tests/e2e/test_tools_e2e.py`, `tests/e2e/test_live_llm.py`

- [ ] **Step 1: Append to `TestToolsE2E` in `tests/e2e/test_tools_e2e.py`** (these auto-skip without `DATABASE_URL`):

```python
    def test_commute_tool_resolves_real_station(self):
        from app.homeos.tools.commute import CommuteTool, CommuteOutput
        with self.engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT station_name FROM mrt_stations "
                "WHERE status = 'operational' LIMIT 1").fetchone()
        if row is None:
            self.skipTest("no MRT stations ingested")
        output = CommuteOutput.model_validate(CommuteTool().fetch(
            self.repo, self.block_id, {"work_locations": [row[0]]}))
        self.assertTrue(output.available)
        self.assertTrue(output.destinations[0].resolved)
        self.assertGreater(output.worst_commute_min, 0)

    def test_bus_routes_tool_is_honest_about_empty_tables(self):
        """Compose DB ships 0 bus_stops/bus_routes rows (no LTA key): the tool
        must say unavailable, never fabricate coverage. If routes ARE ingested,
        it must report them."""
        from app.homeos.tools.bus_routes import BusRoutesTool, BusRoutesOutput
        with self.engine.connect() as conn:
            route_rows = conn.exec_driver_sql("SELECT count(*) FROM bus_routes").scalar()
        output = BusRoutesOutput.model_validate(
            BusRoutesTool().fetch(self.repo, self.block_id, {}))
        if route_rows == 0:
            self.assertFalse(output.available)
            self.assertEqual(output.services, [])
        else:
            self.assertTrue(output.available)
```

Match the class's existing setUp/attribute names — it uses `_connect()`; check the first 60 lines of the file and reuse its `self.engine` / `self.repo` / `self.block_id` attributes exactly as the existing tests do.

- [ ] **Step 2: `tests/e2e/test_live_llm.py`** — the location live test picks up the new tools automatically via `spec.tool_names`; just rename for honesty:

```python
    def test_location_agent_calls_location_tools(self):
        self._assert_agent_calls_its_spec_tools("location")
```

(replacing `test_location_agent_calls_proximity`). `test_spec_coverage_is_complete` needs no change — the agent-name set is unchanged.

- [ ] **Step 3: Run E2E against compose** (from the MAIN checkout root, since docker compose + run_e2e live there; export `E2E` env if run_e2e supports targeting — otherwise run pytest directly with the compose `DATABASE_URL` from the worktree's backend dir):

```bash
cd /Users/moethu/Documents/Codex/hack/estate-finder && python run_e2e.py
```

If compose cannot start in this environment, run `$VENV -m pytest tests/e2e -q` from the worktree (they skip cleanly) and note in the PR that E2E ran as skips locally.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_tools_e2e.py tests/e2e/test_live_llm.py
git commit -m "test(homeos): e2e commute resolution + honest empty-bus-data path"
```

---

### Task 11: Full verification

- [ ] **Step 1: Full offline suite**

Run: `$VENV -m pytest tests/ -q`
Expected: everything passes except the 3 known `test_homeos_stream` baseline failures and the usual 16 skips (e2e/live without env).

- [ ] **Step 2: Quick smoke** — confirm the catalogue self-describes the new tools:

```bash
$VENV -c "
from app.homeos.wiring import setup
import app.homeos.wiring as w
setup()
names = [t['name'] for t in w.tool_repository.describe_tools()]
assert 'commute' in names and 'bus_routes' in names, names
spec = w.tool_repository.get_agent('location')
print('location tools:', spec.tool_names)
print('activating prefs:', [(d.field, d.default) for t in ('commute','bus_routes')
      for d in w.tool_repository.get_tool(t).spec.activating_prefs])
"
```

Expected output includes `location tools: ['proximity', 'commute', 'bus_routes']`.

- [ ] **Step 3:** Use superpowers:verification-before-completion, then superpowers:finishing-a-development-branch (PR per repo convention; PR body must list the three approved deviations above so Spec 1's implementer sees the `PrefDimension` shim landed here).

---

## Deferred to Spec 1 (do not implement here)

- `review_dimensions()` on ToolRepository; `_preference_review` gate in `pipeline.py`
- Tests that the review asks "where do you work?" / "do you rely on buses?"
- The `run_e2e.py --live` journey "I work near Tampines → review does NOT re-ask" (needs the gate)
