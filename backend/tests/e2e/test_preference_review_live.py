"""North-star LIVE test: '4 ROOM under $400k' narrows to ~3 real blocks, and the
stream must pause ONCE at a consolidated preference review BEFORE deep analysis,
then complete after 'proceed'. Real PostGIS + real model.

Costs ~6-14 billed calls — opt in:  python run_e2e.py --live
"""
import asyncio
import os
import unittest

from tests.e2e.test_tools_e2e import _connect

PROFILE = "Looking for a 4 ROOM flat, budget $400k."


class TestPreferenceReviewLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("LIVE_LLM") != "1":
            raise unittest.SkipTest("set LIVE_LLM=1 (or run_e2e.py --live) for live model tests")
        if not os.environ.get("AI_GATEWAY_API_KEY"):
            raise unittest.SkipTest("AI_GATEWAY_API_KEY not set — no live provider")
        cls.engine, cls.repo = _connect()
        from app.homeos.wiring import setup
        setup()

    def test_narrow_search_pauses_at_review_before_deep_analysis(self):
        from app.homeos.pipeline import investigate_stream, refine_stream

        async def run():
            events = []
            async for e in investigate_stream(self.repo, PROFILE, limit=3):
                events.append(e)
            # answer at most 2 questions (review + safety margin), then expect done
            for _ in range(2):
                if not events or events[-1]["event"] != "clarifying_question":
                    break
                case_id = events[-1]["case_id"]
                async for e in refine_stream(self.repo, case_id, "proceed"):
                    events.append(e)
            return events
        events = asyncio.run(run())

        # the live profile agent must have produced a narrow search (sanity)
        searches = [e for e in events if e.get("agent") == "search"
                    and e["event"] == "agent_summary" and "data" in e]
        self.assertTrue(searches, "no search summary event")
        count = searches[0]["data"]["candidates_found"]
        self.assertLessEqual(
            count, 10,
            f"expected a narrow search (~3 blocks) for {PROFILE!r}, got {count} — "
            "if the live model dropped a constraint, tighten PROFILE")

        # THE feature: exactly one consolidated review, BEFORE deep analysis
        reviews = [e for e in events
                   if e["event"] == "clarifying_question"
                   and e.get("field") == "preference_review"]
        self.assertEqual(
            len(reviews), 1,
            "the stream must pause exactly once at a preference review "
            f"(clarifying events: {[e.get('field') for e in events if e['event'] == 'clarifying_question']})")
        self.assertIn("proceed", reviews[0]["question"])
        review_idx = events.index(reviews[0])
        deep_idx = [i for i, e in enumerate(events)
                    if e.get("agent") in ("market", "location", "risk")]
        self.assertTrue(deep_idx, "journey must reach deep analysis after 'proceed'")
        self.assertLess(review_idx, min(deep_idx))

        # journey completes against the real 3 blocks
        self.assertEqual(events[-1]["event"], "case_done")
        self.assertGreaterEqual(len(events[-1]["shortlist"]), 1)

        print(f"\n  review question:\n  {reviews[0]['question']}")


if __name__ == "__main__":
    unittest.main()
