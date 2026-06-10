import json
import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.homeos import case_store as homeos_case_store


class TestHomeOSStreamApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.homeos.wiring import setup as homeos_setup
        homeos_setup()

    def setUp(self):
        self.client = TestClient(app)
        homeos_case_store._cases.clear()

    def _collect_stream(self, profile_text: str, limit: int = 1) -> list[dict]:
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": profile_text, "limit": limit},
        ) as response:
            lines = [line for line in response.iter_lines() if line.startswith("data:")]
        return [json.loads(line[5:]) for line in lines]

    def test_investigate_stream_returns_sse_events(self):
        events = self._collect_stream("Family 4 room 800k schools.")
        self.assertEqual(events[0]["status_code"] if "status_code" in events[0] else 200, 200)
        event_types = [e["event"] for e in events]
        self.assertIn("agent_start", event_types)
        # Stream ends with case_done or clarifying_question (if many candidates)
        self.assertTrue(
            "case_done" in event_types or "clarifying_question" in event_types,
            f"Expected terminal event, got: {event_types}",
        )

    def test_stream_returns_200_with_event_stream(self):
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": "Family 4 room 800k schools.", "limit": 1},
        ) as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/event-stream", response.headers["content-type"])
            # Consume stream
            for _ in response.iter_lines():
                pass

    def test_list_cases_returns_cases_after_investigation(self):
        self._collect_stream("Family 4 room 800k schools.")
        res = self.client.get("/homeos/cases")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json()), 1)

    def test_get_case_returns_case_with_pipeline(self):
        events = self._collect_stream("Family 4 room 800k schools.")
        # Case is stored regardless of whether stream stopped at refining or done
        cases = homeos_case_store.list_cases()
        self.assertGreater(len(cases), 0)
        case_id = cases[0]["case_id"]
        res = self.client.get(f"/homeos/cases/{case_id}")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["case_id"], case_id)
        self.assertIn("pipeline", body)
        self.assertIn("shortlist", body)

    def test_chat_in_case_requires_valid_case_id(self):
        with self.client.stream(
            "POST",
            "/homeos/cases/nonexistent-id/chat",
            json={"message": "Why this block?"},
        ) as response:
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
