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

    def test_investigate_stream_tags_case_with_user(self):
        async def run():
            async for _event in investigate_stream(
                self.repo, "Family wanting 4 room near MRT.", limit=1, user_id=555
            ):
                pass
        asyncio.run(run())
        # The created case must carry the caller's user_id.
        case = next(iter(homeos_case_store._cases.values()))
        self.assertEqual(case["user_id"], 555)

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

    def test_stream_asks_pref_dims_before_analysis(self):
        # "4 room" alone matches >5 blocks, so the gate must ask before analysing.
        events = self._collect_stream("4 room", limit=1)
        q_events = [e for e in events if e["event"] == "clarifying_question"]
        self.assertTrue(q_events, "expected at least one clarifying question before deep analysis")
        for q in q_events:
            self.assertNotEqual(
                q.get("field"), "preference_review",
                "preference_review catch-all field must no longer be used",
            )
            self.assertIsNotNone(q.get("field"))
        last_q_idx = max(events.index(q) for q in q_events)
        deep_idx = [i for i, e in enumerate(events)
                    if e.get("agent") in ("market", "location", "risk")]
        if deep_idx:
            self.assertLess(last_q_idx, min(deep_idx))

    def test_fully_specified_profile_skips_set_dims(self):
        events = self._collect_stream(
            "4 room in TAMPINES max 800k near MRT 2 primary schools.", limit=1)
        q_fields = [e.get("field") for e in events if e["event"] == "clarifying_question"]
        # Verify no preference_review catch-all, and that only specific fields are asked
        self.assertNotIn("preference_review", q_fields)
        for q_field in q_fields:
            self.assertIsNotNone(q_field, "all clarifying questions must have a field")

    def test_profile_with_work_and_no_car_skips_those_dims(self):
        events = self._collect_stream(
            "4 room in TAMPINES max 800k near MRT 2 primary schools. "
            "I work at Raffles Place and have no car.",
            limit=1,
        )
        q_fields = [e.get("field") for e in events if e["event"] == "clarifying_question"]
        self.assertNotIn("work_locations", q_fields)
        self.assertNotIn("bus_reliance", q_fields)

    def test_stream_emits_lifestyle_agent_events(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        lifestyle_starts = [e for e in events if e["event"] == "agent_start" and e["agent"] == "lifestyle"]
        self.assertGreaterEqual(len(lifestyle_starts), 1)
        self.assertIsNotNone(lifestyle_starts[0]["block_id"])

    def test_stream_lifestyle_runs_after_risk(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        agent_starts = [e for e in events if e["event"] == "agent_start" and e["agent"] in ("risk", "lifestyle")]
        agents_in_order = [e["agent"] for e in agent_starts]
        risk_idx = next((i for i, a in enumerate(agents_in_order) if a == "risk"), None)
        lifestyle_idx = next((i for i, a in enumerate(agents_in_order) if a == "lifestyle"), None)
        self.assertIsNotNone(risk_idx)
        self.assertIsNotNone(lifestyle_idx)
        self.assertGreater(lifestyle_idx, risk_idx)

    def test_stream_emits_lifestyle_summary_with_narrative(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        ls_summaries = [e for e in events if e["event"] == "agent_summary" and e["agent"] == "lifestyle"]
        self.assertGreaterEqual(len(ls_summaries), 1)
        self.assertIn("narrative", ls_summaries[0])
        self.assertIsInstance(ls_summaries[0]["narrative"], str)

    def test_shortlist_rows_include_lifestyle_score_and_commute_band(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        case_done = next(e for e in events if e["event"] == "case_done")
        for row in case_done["shortlist"]:
            with self.subTest(block_id=row["block_id"]):
                self.assertIn("lifestyle_score", row)
                self.assertIn("commute_band", row)

    def test_stream_lifestyle_events_stored_in_case(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        case_id = next(e["case_id"] for e in events if e["event"] == "case_done")
        case = homeos_case_store.get_case(case_id)
        pipeline_agents = [e.get("agent") for e in case["pipeline"]]
        self.assertIn("lifestyle", pipeline_agents)

    # ── Proceed command + small-set auto-analysis ────────────────────────────

    def test_proceed_command_skips_remaining_questions(self):
        """Saying 'proceed' must go straight to deep analysis, not ask more."""
        async def run():
            events = []
            async for e in investigate_stream(self.repo, "4 room", limit=2):
                events.append(e)
            # 12 candidates (>5) → investigate should ask at least one question
            self.assertEqual(events[-1]["event"], "clarifying_question", events[-1])
            case_id = events[-1]["case_id"]
            refine_events = []
            async for e in refine_stream(self.repo, case_id, "proceed"):
                refine_events.append(e)
            return refine_events
        refine_events = asyncio.run(run())
        self.assertEqual(
            [e for e in refine_events if e["event"] == "clarifying_question"], [],
            "'proceed' must not produce any further clarifying questions",
        )
        self.assertTrue(
            [e for e in refine_events if e["event"] == "case_done"],
            "'proceed' must reach deep analysis (case_done)",
        )

    def test_small_set_asks_to_confirm_then_proceeds(self):
        """<=5 candidates → one 'ready_to_proceed' confirm prompt, not auto-run.

        Clicking the Proceed chip (sends 'proceed') then runs deep analysis.
        """
        async def investigate():
            events = []
            async for e in investigate_stream(
                self.repo, "Family 4 room 800k schools.", limit=2):
                events.append(e)
            return events
        events = asyncio.run(investigate())
        qs = [e for e in events if e["event"] == "clarifying_question"]
        self.assertEqual(len(qs), 1, "small set should emit exactly one confirm prompt")
        self.assertEqual(qs[0]["field"], "ready_to_proceed")
        self.assertEqual(
            [e for e in events if e["event"] == "case_done"], [],
            "must wait for the user to proceed, not auto-run analysis",
        )

        case_id = qs[0]["case_id"]

        async def proceed():
            ev = []
            async for e in refine_stream(self.repo, case_id, "proceed"):
                ev.append(e)
            return ev
        proceed_events = asyncio.run(proceed())
        self.assertEqual(
            [e for e in proceed_events if e["event"] == "clarifying_question"], [],
            "'proceed' from the confirm prompt must not ask anything more",
        )
        self.assertTrue(
            [e for e in proceed_events if e["event"] == "case_done"],
            "clicking Proceed must run deep analysis (case_done)",
        )


if __name__ == "__main__":
    unittest.main()
