import asyncio
import os
import unittest
from unittest.mock import patch

from app.data.seed import build_seeded_repo
from app.services import homeos_case_store
from app.services.homeos import chat_in_case, investigate_homeos_profile, investigate_stream
from app.services.homeos_mock_agents import mock_delay_seconds


class TestHomeOSMockAgents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=4, months=6)

    def setUp(self):
        homeos_case_store._cases.clear()

    def _collect_mock_stream(self, profile_text: str, limit: int = 1) -> list[dict]:
        async def run():
            events = []
            with patch.dict(
                os.environ,
                {"HOMEOS_AGENT_MODE": "mock", "HOMEOS_MOCK_DELAY_SECONDS": "0"},
            ):
                async for event in investigate_stream(self.repo, profile_text, limit=limit):
                    events.append(event)
            return events

        return asyncio.run(run())

    def test_mock_stream_uses_deterministic_profile_summary(self):
        events = self._collect_mock_stream("Family 4 room 800k schools.", limit=1)
        summaries = [
            e for e in events
            if e["event"] == "agent_summary" and e["agent"] == "profile"
        ]
        self.assertEqual(len(summaries), 1)
        self.assertIn("Mock profile", summaries[0]["narrative"])

    def test_mock_stream_uses_deterministic_block_agent_summaries(self):
        events = self._collect_mock_stream("Family 4 room 800k schools.", limit=1)
        narratives = {
            e["agent"]: e["narrative"]
            for e in events
            if e["event"] == "agent_summary" and e.get("block_id") is not None
        }
        self.assertIn("Mock market", narratives["market"])
        self.assertIn("Mock location", narratives["location"])
        self.assertIn("Mock risk", narratives["risk"])

    def test_mock_chat_returns_grounded_demo_answer(self):
        events = self._collect_mock_stream("Family 4 room 800k schools.", limit=1)
        case_id = events[-1]["case_id"]

        async def run_chat():
            chunks = []
            with patch.dict(
                os.environ,
                {"HOMEOS_AGENT_MODE": "mock", "HOMEOS_MOCK_DELAY_SECONDS": "0"},
            ):
                async for chunk in chat_in_case(case_id, "Why did you pick this block?"):
                    chunks.append(chunk)
            return chunks

        chunks = asyncio.run(run_chat())
        answer = "".join(chunks)
        self.assertIn("Mock HomeOS", answer)
        self.assertIn("pipeline", answer.lower())

    def test_mock_legacy_investigate_returns_demo_avatar(self):
        with patch.dict(
            os.environ,
            {"HOMEOS_AGENT_MODE": "mock", "HOMEOS_MOCK_DELAY_SECONDS": "0"},
        ):
            result = investigate_homeos_profile(
                self.repo, "Family 4 room 800k schools.", limit=1
            )
        self.assertEqual(result["avatar"]["label"], "Mock HomeOS Agent")
        self.assertIn("Mock profile", result["avatar"]["summary"])
        self.assertGreater(len(result["shortlist"]), 0)

    def test_mock_delay_defaults_to_one_second_and_can_be_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(mock_delay_seconds(), 1.0)
        with patch.dict(os.environ, {"HOMEOS_MOCK_DELAY_SECONDS": "0"}):
            self.assertEqual(mock_delay_seconds(), 0.0)


if __name__ == "__main__":
    unittest.main()
