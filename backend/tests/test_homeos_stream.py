import asyncio
import os
import unittest
from unittest.mock import patch

from app.data.seed import build_seeded_repo
from app.homeos.pipeline import chat_in_case, investigate_stream, refine_stream
from app.homeos import case_store as homeos_case_store

_env_patch = patch.dict(os.environ, {
    "HOMEOS_AGENT_MODE": "mock",
    "HOMEOS_MOCK_DELAY_SECONDS": "0",
    "LLM_PROVIDER": "test",
    "AI_GATEWAY_API_KEY": "",
})


class TestHomeOSStream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _env_patch.start()
        cls.addClassCleanup(_env_patch.stop)
        from app.homeos.wiring import setup as homeos_setup
        homeos_setup()
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=4, months=6)

    def setUp(self):
        homeos_case_store._cases.clear()

    def _collect_stream(self, profile_text: str, limit: int = 2,
                        max_rounds: int = 8) -> list[dict]:
        """Run investigate_stream, auto-answering clarifying questions
        (including the preference review) with 'proceed' until case_done."""
        async def run():
            events = []
            async for event in investigate_stream(self.repo, profile_text, limit=limit):
                events.append(event)
            for _ in range(max_rounds):
                if not events or events[-1]["event"] != "clarifying_question":
                    break
                case_id = events[-1]["case_id"]
                async for event in refine_stream(self.repo, case_id, "proceed"):
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
        self.assertGreaterEqual(len(summaries), 1)
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
        self.assertGreaterEqual(len(case["conversation"]), 2)
        self.assertEqual(case["conversation"][-1]["role"], "assistant")

    def test_stream_asks_preference_review_before_analysis(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        reviews = [e for e in events
                   if e["event"] == "clarifying_question"
                   and e.get("field") == "preference_review"]
        self.assertEqual(len(reviews), 1, "preference review must fire exactly once")
        self.assertIn("proceed", reviews[0]["question"])
        self.assertIn("Where do you", reviews[0]["question"])
        self.assertIn("rely on buses", reviews[0]["question"])
        review_idx = events.index(reviews[0])
        deep_idx = [i for i, e in enumerate(events)
                    if e.get("agent") in ("market", "location", "risk")]
        if deep_idx:
            self.assertLess(review_idx, min(deep_idx))

    def test_fully_specified_profile_skips_review_dimensions_it_set(self):
        events = self._collect_stream(
            "4 room in TAMPINES max 800k near MRT 2 primary schools.", limit=1)
        reviews = [e for e in events
                   if e["event"] == "clarifying_question"
                   and e.get("field") == "preference_review"]
        for r in reviews:
            self.assertNotIn("budget ceiling", r["question"])
            self.assertNotIn("Flat type", r["question"])

    def test_profile_with_work_and_no_car_skips_new_tool_questions(self):
        events = self._collect_stream(
            "4 room in TAMPINES max 800k near MRT 2 primary schools. "
            "I work at Raffles Place and have no car.",
            limit=1,
        )
        reviews = [e for e in events
                   if e["event"] == "clarifying_question"
                   and e.get("field") == "preference_review"]
        for r in reviews:
            self.assertNotIn("Where do you", r["question"])
            self.assertNotIn("rely on buses", r["question"])


if __name__ == "__main__":
    unittest.main()
