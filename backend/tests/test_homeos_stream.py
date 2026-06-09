import asyncio
import unittest

from app.data.seed import build_seeded_repo
from app.homeos.pipeline import chat_in_case, investigate_stream
from app.homeos import case_store as homeos_case_store


class TestHomeOSStream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.homeos.wiring import setup as homeos_setup
        homeos_setup()
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=4, months=6)

    def setUp(self):
        homeos_case_store._cases.clear()

    def _collect_stream(self, profile_text: str, limit: int = 2) -> list[dict]:
        async def run():
            events = []
            async for event in investigate_stream(
                self.repo, profile_text, limit=limit
            ):
                events.append(event)
            return events
        return asyncio.run(run())

    def test_stream_starts_with_profile_agent_start(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        first = events[0]
        self.assertEqual(first["event"], "agent_start")
        self.assertEqual(first["agent"], "profile")
        self.assertIsNone(first["block_id"])

    def test_stream_contains_agent_summary_for_profile(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        summaries = [e for e in events if e["event"] == "agent_summary" and e["agent"] == "profile"]
        self.assertEqual(len(summaries), 1)
        self.assertIn("narrative", summaries[0])

    def test_stream_ends_with_case_done(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        last = events[-1]
        self.assertEqual(last["event"], "case_done")
        self.assertIn("case_id", last)
        self.assertIn("shortlist", last)

    def test_stream_creates_case_in_store(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        case_done = events[-1]
        case = homeos_case_store.get_case(case_done["case_id"])
        self.assertIsNotNone(case)
        self.assertEqual(case["status"], "done")
        self.assertGreater(len(case["pipeline"]), 0)

    def test_stream_emits_per_block_agent_events(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=2)
        market_starts = [e for e in events if e["event"] == "agent_start" and e["agent"] == "market"]
        self.assertGreaterEqual(len(market_starts), 1)
        for e in market_starts:
            self.assertIsNotNone(e["block_id"])

    def test_chat_in_case_streams_response(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        case_id = events[-1]["case_id"]

        async def run_chat():
            chunks = []
            async for chunk in chat_in_case(case_id, "Why did you pick this block?"):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(run_chat())
        self.assertGreater(len(chunks), 0)
        full_text = "".join(chunks)
        self.assertGreater(len(full_text), 0)
        case = homeos_case_store.get_case(case_id)
        self.assertEqual(len(case["conversation"]), 2)
        self.assertEqual(case["conversation"][0]["role"], "user")
        self.assertEqual(case["conversation"][1]["role"], "assistant")


if __name__ == "__main__":
    unittest.main()
