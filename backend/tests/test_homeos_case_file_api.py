import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.homeos import case_store

client = TestClient(app)


class TestCaseFileApi(unittest.TestCase):
    def setUp(self):
        case_store._cases.clear()

    def test_uses_assembler_when_case_id_present(self):
        case = case_store.create_case("family with kids budget 500k near mrt")
        cid = case["case_id"]
        bid = 4242
        case_store.append_event(cid, {
            "event": "agent_data", "agent": "market", "block_id": bid,
            "data": {"transaction_count": 5, "median_price": 400000.0,
                     "median_psf": 410.0, "window_months": 6, "summary": "ok"},
        })
        case_store.append_event(cid, {
            "event": "agent_data", "agent": "risk", "block_id": bid,
            "data": {"watchouts": []},
        })
        case_store.set_shortlist(cid, [{
            "block_id": bid, "block_number": "1", "street_name": "TEST ST",
            "town": "WOODLANDS", "worth_viewing_score": 50.0, "verdict": "Maybe view",
            "confidence": "medium", "top_reasons": [], "top_watchouts": [],
        }])
        resp = client.post(
            f"/homeos/case-file/{bid}",
            json={"profile_text": "family with kids budget 500k near mrt", "case_id": cid},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["block_id"], bid)
        self.assertIn("trace", body)
        self.assertEqual(body["evidence"]["recent_sales"]["transaction_count"], 5)

    def test_falls_back_to_recompute_when_block_not_in_case(self):
        case = case_store.create_case("family with kids budget 500k near mrt")
        cid = case["case_id"]
        # No events for this block -> assembler returns None -> recompute path runs.
        resp = client.post(
            "/homeos/case-file/999999",
            json={"profile_text": "family with kids budget 500k near mrt", "case_id": cid},
        )
        # recompute raises ValueError("block not found") -> 404
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
