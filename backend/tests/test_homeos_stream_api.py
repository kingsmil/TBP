import json
import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.services import homeos_case_store


class TestHomeOSStreamApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        homeos_case_store._cases.clear()

    def test_investigate_stream_returns_sse_events(self):
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": "Family 4 room 800k schools.", "limit": 1},
        ) as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/event-stream", response.headers["content-type"])
            lines = [line for line in response.iter_lines() if line.startswith("data:")]
            events = [json.loads(line[5:]) for line in lines]
            event_types = [e["event"] for e in events]
            self.assertIn("agent_start", event_types)
            self.assertIn("case_done", event_types)

    def test_list_cases_returns_cases_after_investigation(self):
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": "Family 4 room 800k schools.", "limit": 1},
        ) as response:
            for _ in response.iter_lines():
                pass
        res = self.client.get("/homeos/cases")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json()), 1)

    def test_get_case_returns_full_case(self):
        case_id = None
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": "Family 4 room 800k schools.", "limit": 1},
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data:"):
                    evt = json.loads(line[5:])
                    if evt["event"] == "case_done":
                        case_id = evt["case_id"]
        self.assertIsNotNone(case_id)
        res = self.client.get(f"/homeos/cases/{case_id}")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["case_id"], case_id)
        self.assertIn("pipeline", body)
        self.assertIn("shortlist", body)

    def test_chat_in_case_returns_sse_text(self):
        case_id = None
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": "Family 4 room 800k schools.", "limit": 1},
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data:"):
                    evt = json.loads(line[5:])
                    if evt["event"] == "case_done":
                        case_id = evt["case_id"]
        with self.client.stream(
            "POST",
            f"/homeos/cases/{case_id}/chat",
            json={"message": "Why did you pick this block?"},
        ) as response:
            self.assertEqual(response.status_code, 200)
            chunks = list(response.iter_lines())
            self.assertGreater(len(chunks), 0)


if __name__ == "__main__":
    unittest.main()
