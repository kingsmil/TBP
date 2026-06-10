"""End-to-end spec for per-user HomeOS session persistence.

This is the OUTSIDE-IN driver for the "persist sessions per user" feature. It
exercises the real HTTP API (TestClient) against the real Postgres
`homeos_cases` table, simulating two distinct authenticated users via FastAPI
dependency overrides (the repo's .env sets AUTH_REQUIRED=false, which otherwise
collapses every caller to user 0).

It is RED until the backend tasks are implemented:
  - migration 0010_homeos_cases.sql (table)
  - case_store write-through + user scoping
  - investigate_stream(user_id=...) + user-scoped/ownership-checked routes

Block data is supplied by an in-memory seeded repo so the spec does not depend
on a seeded PostGIS instance; persistence still goes through real Postgres
because case_store opens its own connection.

Skips automatically when DATABASE_URL is unset or Postgres is unreachable.
"""
from __future__ import annotations

import json
import os
import unittest

# Importing app.config loads the repo .env (DATABASE_URL, AUTH_REQUIRED, …) into
# os.environ. Must happen before the skipUnless check below runs at import time.
import app.config  # noqa: F401


def _db_reachable() -> bool:
    if not os.environ.get("DATABASE_URL"):
        return False
    try:
        from app.db.session import get_engine
        conn = get_engine().raw_connection()
        conn.close()
        return True
    except Exception:
        return False


@unittest.skipUnless(_db_reachable(), "needs a reachable Postgres (DATABASE_URL)")
class TestSessionPersistenceE2E(unittest.TestCase):
    PROFILE = "Family looking for a 4 room flat under 800k near MRT and schools."

    @classmethod
    def setUpClass(cls):
        os.environ["HOMEOS_AGENT_MODE"] = "mock"  # no LLM, deterministic narratives
        from app.homeos.wiring import setup as homeos_setup
        homeos_setup()

        # Ensure schema exists (users + homeos_cases). Idempotent.
        from app.db import migrate
        migrate.main()

        # Two real users so the homeos_cases.user_id FK is satisfied.
        cls.user_a = cls._ensure_user("e2e_persist_a@test.local")
        cls.user_b = cls._ensure_user("e2e_persist_b@test.local")

        # Seeded in-memory repo provides candidate blocks without needing PostGIS.
        from app.data.seed import build_seeded_repo
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=5, months=6)

    @staticmethod
    def _ensure_user(email: str) -> int:
        from app.db.session import get_engine
        conn = get_engine().raw_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash, is_subscribed)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (email) DO UPDATE SET is_subscribed = TRUE
                    RETURNING id
                    """,
                    (email, "x"),
                )
                uid = cur.fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        return uid

    def setUp(self):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.api.auth import CurrentUser, require_subscribed
        from app.api.main import app
        from app.homeos import case_store

        self.app = app
        self.case_store = case_store
        self.require_subscribed = require_subscribed
        self._CurrentUser = CurrentUser

        case_store._cases.clear()
        self.client = TestClient(app)

        # Swappable current user + seeded repo.
        self._current = self._CurrentUser(user_id=self.user_a, email="a", is_subscribed=True)
        app.dependency_overrides[require_subscribed] = lambda: self._current
        app.dependency_overrides[deps.get_repository] = lambda: self.repo

    def tearDown(self):
        from app.api import deps
        self.app.dependency_overrides.pop(self.require_subscribed, None)
        self.app.dependency_overrides.pop(deps.get_repository, None)
        self._delete_cases_for(self.user_a)
        self._delete_cases_for(self.user_b)

    def _delete_cases_for(self, user_id: int) -> None:
        from app.db.session import get_engine
        conn = get_engine().raw_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM homeos_cases WHERE user_id = %s", (user_id,))
            conn.commit()
        except Exception:
            # Table may not exist yet (feature unimplemented) — cleanup is best-effort.
            conn.rollback()
        finally:
            conn.close()

    def _act_as(self, user_id: int) -> None:
        self._current = self._CurrentUser(user_id=user_id, email=str(user_id), is_subscribed=True)

    def _run_investigation(self, profile: str, limit: int = 1) -> str:
        """Drive a full investigation stream and return the resulting case_id."""
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": profile, "limit": limit},
        ) as response:
            self.assertEqual(response.status_code, 200)
            events = [
                json.loads(line[5:])
                for line in response.iter_lines()
                if line.startswith("data:")
            ]
        for event in events:
            if event.get("case_id"):
                return event["case_id"]
        self.fail(f"no case_id in stream events: {[e.get('event') for e in events]}")

    # ── The spec ───────────────────────────────────────────────────────────────

    def test_investigation_persists_under_the_owner(self):
        case_id = self._run_investigation(self.PROFILE)

        listed = self.client.get("/homeos/cases").json()
        self.assertIn(case_id, [c["case_id"] for c in listed],
                      "owner's case must appear in their case list")

        full = self.client.get(f"/homeos/cases/{case_id}")
        self.assertEqual(full.status_code, 200)
        body = full.json()
        self.assertEqual(body["case_id"], case_id)
        self.assertGreater(len(body["pipeline"]), 0, "pipeline events must be persisted")

    def test_cases_are_scoped_per_user(self):
        case_id = self._run_investigation(self.PROFILE)

        # User B must neither see nor open user A's case.
        self._act_as(self.user_b)
        listed_b = self.client.get("/homeos/cases").json()
        self.assertNotIn(case_id, [c["case_id"] for c in listed_b],
                         "another user must not see this case in their list")
        self.assertEqual(
            self.client.get(f"/homeos/cases/{case_id}").status_code, 404,
            "another user opening the case must get 404 (existence not leaked)",
        )

    def test_case_survives_server_restart(self):
        case_id = self._run_investigation(self.PROFILE)
        before = self.client.get(f"/homeos/cases/{case_id}").json()

        # Simulate a process restart: drop the in-memory cache entirely.
        self.case_store._cases.clear()

        after = self.client.get(f"/homeos/cases/{case_id}")
        self.assertEqual(after.status_code, 200,
                         "case must rehydrate from Postgres after cache loss")
        reloaded = after.json()
        self.assertEqual(reloaded["case_id"], case_id)
        self.assertEqual(
            len(reloaded["pipeline"]), len(before["pipeline"]),
            "reopened case must show the same pipeline output as originally streamed",
        )
        self.assertEqual(reloaded["shortlist"], before["shortlist"],
                         "reopened case must show the same shortlist")


if __name__ == "__main__":
    unittest.main()
