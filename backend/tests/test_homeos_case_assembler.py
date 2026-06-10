import unittest

from app.homeos import case_store
from app.homeos.case_assembler import assemble_case_file_from_case


def _seed_case():
    case = case_store.create_case("family with kids budget 500k near mrt")
    cid = case["case_id"]
    bid = 812
    case_store.append_event(cid, {
        "event": "agent_data", "agent": "market", "block_id": bid,
        "data": {"transaction_count": 8, "median_price": 397500.0,
                 "median_psf": 416.0, "window_months": 6,
                 "summary": "8 sales support price confidence.",
                 "narrative": "8 sales support price confidence.",
                 "confidence": "high"},
    })
    case_store.append_event(cid, {
        "event": "tool_calls", "agent": "market", "block_id": bid,
        "tool_calls": [{"tool_name": "recent_transactions",
                        "args": {"block_id": bid}, "result": {"count": 8}}],
    })
    case_store.append_event(cid, {
        "event": "agent_summary", "agent": "market", "block_id": bid,
        "narrative": "Market looks solid.",
    })
    case_store.append_event(cid, {
        "event": "agent_data", "agent": "location", "block_id": bid,
        "data": {"connections": [{"type": "mrt", "signal": "moderate"}]},
    })
    case_store.append_event(cid, {
        "event": "agent_data", "agent": "risk", "block_id": bid,
        "data": {"future_mrt": None, "future_supply": "1 BTO in 2027",
                 "watchouts": ["One BTO in 2027 may soften resale."]},
    })
    case_store.set_shortlist(cid, [{
        "block_id": bid, "block_number": "8", "street_name": "MARSILING DR",
        "town": "WOODLANDS", "worth_viewing_score": 53.8, "verdict": "Maybe view",
        "confidence": "high",
        "top_reasons": [{"text": "Recent comparable sales support the budget.", "source": "market"}],
        "top_watchouts": [{"text": "One BTO in 2027 may soften resale.", "source": "risk"}],
    }])
    return cid, bid


class TestCaseAssembler(unittest.TestCase):
    def setUp(self):
        case_store._cases.clear()

    def test_assembles_case_file_from_stored_events(self):
        cid, bid = _seed_case()
        cf = assemble_case_file_from_case(cid, bid)
        self.assertIsNotNone(cf)
        self.assertEqual(cf["block_id"], bid)
        self.assertEqual(cf["verdict"], "Maybe view")
        self.assertEqual(cf["worth_viewing_score"], 53.8)
        self.assertEqual(cf["top_reasons"][0]["source"], "market")
        self.assertEqual(cf["evidence"]["recent_sales"]["transaction_count"], 8)
        self.assertEqual(cf["evidence"]["recent_sales"]["summary"],
                         "8 sales support price confidence.")
        self.assertTrue(all(isinstance(r, str) for r in cf["evidence"]["risks"]))
        self.assertTrue(len(cf["evidence"]["agent_questions"]) > 0)

    def test_trace_contains_tool_calls(self):
        cid, bid = _seed_case()
        cf = assemble_case_file_from_case(cid, bid)
        market_trace = next(t for t in cf["trace"] if t["agent"] == "market")
        self.assertEqual(market_trace["tool_calls"][0]["tool_name"], "recent_transactions")
        self.assertEqual(market_trace["narrative"], "Market looks solid.")

    def test_returns_none_for_unknown_case(self):
        self.assertIsNone(assemble_case_file_from_case("no-such-case", 1))

    def test_returns_none_for_block_not_in_case(self):
        cid, _ = _seed_case()
        self.assertIsNone(assemble_case_file_from_case(cid, 999999))


if __name__ == "__main__":
    unittest.main()
