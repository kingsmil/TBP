"""Unit tests for Spec 2: commute + bus_routes tools, activating prefs, scoring watchout."""
import unittest

from app.core.geo import Point
from app.core.models import Block, BlockProximity, BusStop, MrtStation
from pydantic import BaseModel

from app.homeos.framework.spec import AgentSpec, PrefDimension, ToolSpec
from app.homeos.models.avatar import HomeOSPreferences
from app.repositories.memory import InMemoryRepository


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

    def test_no_work_locations_is_unavailable(self):
        from app.homeos.tools.commute import CommuteTool
        result = CommuteTool().fetch(self.repo, 1, {})
        self.assertEqual(result, {"available": False, "destinations": [], "worst_commute_min": None})

    def test_resolves_and_estimates_each_work_location(self):
        from app.homeos.tools.commute import CommuteOutput, CommuteTool
        result = CommuteTool().fetch(self.repo, 1, {"work_locations": ["Raffles Place", "Atlantis"]})
        output = CommuteOutput.model_validate(result)
        self.assertTrue(output.available)
        by_name = {d.name: d for d in output.destinations}
        self.assertIn("Raffles Place", by_name)
        self.assertIn("Atlantis", by_name)
        self.assertIsNotNone(by_name["Raffles Place"].travel_min)
        self.assertIsNone(by_name["Atlantis"].travel_min)
        self.assertEqual(output.worst_commute_min, by_name["Raffles Place"].travel_min)

    def test_worst_commute_is_max(self):
        from app.homeos.tools.commute import CommuteTool
        result = CommuteTool().fetch(self.repo, 1, {"work_locations": ["Raffles Place", "Jurong East"]})
        mins = [d["travel_min"] for d in result["destinations"] if d["travel_min"] is not None]
        self.assertEqual(result["worst_commute_min"], max(mins))

    def test_missing_block_is_unavailable(self):
        from app.homeos.tools.commute import CommuteTool
        result = CommuteTool().fetch(self.repo, 999, {"work_locations": ["Raffles Place"]})
        self.assertFalse(result["available"])
        self.assertEqual(result["destinations"], [])

    def test_spec_declares_activating_pref(self):
        from app.homeos.tools.commute import CommuteOutput, CommuteTool
        spec = CommuteTool.spec
        self.assertIs(spec.output_type, CommuteOutput)
        self.assertEqual(spec.activating_prefs[0].field, "work_locations")


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
        # service 63 boards 01001 at seq 6 - nothing downstream
        self.assertEqual([s["bus_stop_code"] for s in by_no["63"]["stops"]], ["01001"])
        self.assertEqual(reach["reachable_stop_count"], 2)

    def test_stop_with_no_routes_returns_empty_services(self):
        repo = InMemoryRepository()
        repo.add_bus_stops([BusStop("02001", "Lonely", Point(103.9, 1.3))])
        reach = repo.bus_stop_reach("02001")
        self.assertEqual(reach["services"], [])
        self.assertEqual(reach["service_count"], 0)


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


if __name__ == "__main__":
    unittest.main()
