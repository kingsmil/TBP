"""Live E2E: the FULL investigate_stream orchestration with a real model.

Journey (one test): vague profile → clarifying question → refine_stream answer
→ per-block deep analysis → case_done. Real PostGIS data, real LLM.
Spec: docs/superpowers/specs/2026-06-10-investigate-stream-live-e2e-design.md

Costs ~10-11 billed model calls — opt in explicitly:  python run_e2e.py --live
"""
import asyncio
import os
import unittest

from tests.e2e.test_tools_e2e import _connect

# Deliberately vague: no town, so the clarifying gate must fire against ~9k blocks.
PROFILE = (
    "Young family looking for a 4 ROOM flat, budget $750k, "
    "want good primary schools nearby."
)
REFINE_ANSWER = "Tampines please"
MAX_REFINE_ROUNDS = 3  # too-many gate Qs + preference review need headroom
DEEP_AGENTS = ("market", "location", "risk")


def _collect(agen):
    async def run():
        return [event async for event in agen]
    return asyncio.run(run())


class TestInvestigateStreamLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("LIVE_LLM") != "1":
            raise unittest.SkipTest("set LIVE_LLM=1 (or run_e2e.py --live) for live model tests")
        if not os.environ.get("AI_GATEWAY_API_KEY"):
            raise unittest.SkipTest("AI_GATEWAY_API_KEY not set — no live provider")
        from tests.e2e.live_log import LiveRunLog
        cls.log = LiveRunLog("investigate-stream")
        cls.addClassCleanup(lambda: print(f"\n  live log: {cls.log.close()}"))
        cls.engine, cls.repo = _connect()
        from app.homeos.wiring import setup
        setup()

    def _log_events(self, phase: str, events: list[dict]) -> None:
        self.log.section(phase)
        for e in events:
            self.log.record("stream_event", phase=phase, **e)
            kind = e["event"]
            if kind == "agent_summary":
                self.log.line(f"- **{e['agent']}** (block {e.get('block_id')}): {e['narrative']}")
            elif kind == "clarifying_question":
                self.log.line(f"- **clarifying_question** [{e.get('field')}]: {e['question']}")
            elif kind == "case_done":
                self.log.line(f"- **case_done**: shortlist {len(e['shortlist'])} blocks")
                self.log.block(e["shortlist"])

    def test_full_stream_vague_profile_refine_to_case_done(self):
        from app.homeos.pipeline import investigate_stream, refine_stream
        from app.homeos import case_store

        self.log.line(f"profile: {PROFILE!r}")

        # ── Step 1: vague profile must stop at a clarifying question ──────────
        events = _collect(investigate_stream(self.repo, PROFILE, limit=2))
        self._log_events("Step 1 — investigate_stream (vague profile)", events)

        self.assertEqual(events[0]["event"], "agent_start")
        self.assertEqual(events[0]["agent"], "profile")

        questions = [e for e in events if e["event"] == "clarifying_question"]
        dones = [e for e in events if e["event"] == "case_done"]
        self.assertFalse(
            dones,
            "expected clarifying_question, got case_done — model parsed enough "
            "prefs from the vague profile; make PROFILE vaguer")
        self.assertEqual(len(questions), 1)
        first_question = questions[0]["question"]
        self.assertTrue(first_question)
        case_id = questions[0]["case_id"]
        self.assertIsNotNone(case_store.get_case(case_id))
        self.assertEqual(case_store.get_case(case_id)["status"], "refining")

        # ── Step 2: refine; must not re-ask the same question ─────────────────
        asked = [first_question]
        events = _collect(refine_stream(self.repo, case_id, REFINE_ANSWER))
        self._log_events(f"Step 2 — refine_stream({REFINE_ANSWER!r})", events)
        for _ in range(MAX_REFINE_ROUNDS - 1):
            questions = [e for e in events if e["event"] == "clarifying_question"]
            if not questions:
                break
            q = questions[0]["question"]
            self.assertNotIn(
                q, asked,
                f"refine loop regression: same clarifying question repeated: {q!r}")
            asked.append(q)
            events = _collect(refine_stream(self.repo, case_id, "No other preferences."))
            self._log_events("Step 2b — refine_stream('No other preferences.')", events)
        else:
            remaining = [e for e in events if e["event"] == "clarifying_question"]
            self.assertFalse(
                remaining,
                f"never reached deep analysis after {MAX_REFINE_ROUNDS} refinement "
                f"rounds; questions asked: {asked}")

        # ── Preference review must have fired exactly once ────────────────────
        case = case_store.get_case(case_id)
        reviews = [e for e in case["pipeline"]
                   if e.get("event") == "clarifying_question"
                   and e.get("field") == "preference_review"]
        self.assertEqual(len(reviews), 1,
                         f"expected exactly one preference review; got {len(reviews)}")

        # ── Step 3: deep-analysis event grammar per (agent, block) ────────────
        deep = [e for e in events if e.get("agent") in DEEP_AGENTS]
        self.assertTrue(deep, f"no deep-analysis events; events: {[e['event'] for e in events]}")
        block_ids = {e["block_id"] for e in deep}
        for block_id in block_ids:
            for agent in DEEP_AGENTS:
                seq = [e["event"] for e in deep
                       if e["block_id"] == block_id and e["agent"] == agent]
                with self.subTest(block=block_id, agent=agent):
                    self.assertIn("agent_start", seq)
                    self.assertIn("agent_summary", seq)
                    self.assertIn("agent_done", seq)
                    self.assertLess(seq.index("agent_start"), seq.index("agent_summary"))
                    self.assertLess(seq.index("agent_summary"), seq.index("agent_done"))
        for e in deep:
            if e["event"] == "agent_summary":
                self.assertTrue(e["narrative"], f"empty narrative: {e}")
            if e["event"] == "agent_data":
                self.assertIsInstance(e["data"], dict)

        # ── Step 4: completion + persistence ──────────────────────────────────
        last = events[-1]
        self.assertEqual(last["event"], "case_done")
        self.assertEqual(last["case_id"], case_id)
        shortlist = last["shortlist"]
        self.assertTrue(shortlist, "case_done with empty shortlist")
        for row in shortlist:
            self.assertGreaterEqual(row["worth_viewing_score"], 0)
            self.assertLessEqual(row["worth_viewing_score"], 100)
            self.assertTrue(row["verdict"])

        self.assertEqual(case["status"], "done")
        pipeline_events = [e.get("event") for e in case["pipeline"]]
        self.assertIn("clarifying_question", pipeline_events)
        self.assertIn("case_done", pipeline_events)

        print(f"\n  journey: {len(asked)} question(s) → {len(block_ids)} block(s) "
              f"analysed → shortlist {[r['verdict'] for r in shortlist]}")


if __name__ == "__main__":
    unittest.main()
