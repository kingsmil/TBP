"""Tests for the lifestyle sub-agent (Commute Heatmap + Couple Mode + Lifestyle Score)."""
import os
import unittest

os.environ.setdefault("HOMEOS_AGENT_MODE", "mock")

from app.core.geo import Point
from app.data.seed import build_seeded_repo
from app.homeos.sync_agents import lifestyle_analysis_agent
from app.services.commute.models import Destination, Person
from app.services.commute.provider import HeuristicCommuteProvider

_OFFICE = Destination("Office", Point(lon=103.8198, lat=1.3521), visits_per_week=5)


class TestLifestyleSubAgentMockMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=5, months=6)
        cls.provider = HeuristicCommuteProvider(list(cls.repo.mrt_stations()))
        cls.block_id = cls.repo.blocks()[0].block_id

    def test_returns_required_keys(self):
        result = lifestyle_analysis_agent(self.repo, self.block_id)
        for key in ("lifestyle_score", "commute_band", "couple_fairness", "factors", "watchouts", "narrative"):
            with self.subTest(key=key):
                self.assertIn(key, result)

    def test_lifestyle_score_in_range_or_none(self):
        result = lifestyle_analysis_agent(self.repo, self.block_id)
        score = result["lifestyle_score"]
        if score is not None:
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)

    def test_commute_band_set_when_provider_given(self):
        result = lifestyle_analysis_agent(self.repo, self.block_id, provider=self.provider, destinations=[_OFFICE])
        self.assertIn(result["commute_band"], ("green", "yellow", "red"))

    def test_no_commute_band_without_provider(self):
        result = lifestyle_analysis_agent(self.repo, self.block_id)
        self.assertIsNone(result["commute_band"])

    def test_couple_fairness_set_in_couple_mode(self):
        person_a = Person("Alice", (Destination("Work A", Point(lon=103.82, lat=1.35), 5),))
        person_b = Person("Bob",   (Destination("Work B", Point(lon=103.84, lat=1.29), 5),))
        result = lifestyle_analysis_agent(
            self.repo, self.block_id,
            provider=self.provider,
            destinations=[_OFFICE],
            person_a=person_a,
            person_b=person_b,
        )
        self.assertIsNotNone(result["couple_fairness"])
        self.assertGreaterEqual(result["couple_fairness"], 0)
        self.assertLessEqual(result["couple_fairness"], 100)

    def test_no_couple_fairness_without_persons(self):
        result = lifestyle_analysis_agent(self.repo, self.block_id, provider=self.provider, destinations=[_OFFICE])
        self.assertIsNone(result["couple_fairness"])

    def test_narrative_is_non_empty_string(self):
        result = lifestyle_analysis_agent(self.repo, self.block_id, provider=self.provider, destinations=[_OFFICE])
        self.assertIsInstance(result["narrative"], str)
        self.assertGreater(len(result["narrative"]), 0)

    def test_watchout_for_red_commute_band(self):
        """A block far from destinations should produce a red-band watchout if band is red."""
        far_dest = [Destination("Far", Point(lon=200.0, lat=90.0), visits_per_week=50)]
        result = lifestyle_analysis_agent(self.repo, self.block_id, provider=self.provider, destinations=far_dest)
        if result["commute_band"] == "red":
            self.assertTrue(
                any("Commute burden" in w for w in result["watchouts"]),
                msg="Expected commute-burden watchout for red band",
            )

    def test_unknown_block_returns_none_score(self):
        result = lifestyle_analysis_agent(self.repo, block_id=999999)
        self.assertIsNone(result["lifestyle_score"])

    def test_callable_from_sync_agents_module(self):
        from app.homeos import sync_agents
        self.assertTrue(callable(getattr(sync_agents, "lifestyle_analysis_agent")))


if __name__ == "__main__":
    unittest.main()
