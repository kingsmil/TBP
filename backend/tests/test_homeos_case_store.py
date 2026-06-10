import os
import unittest
from unittest.mock import patch

# Loads the repo .env (DATABASE_URL, …) before the skipUnless on the
# persistence class is evaluated at import time.
import app.config  # noqa: F401

from app.homeos.case_store import (
    append_event,
    append_message,
    create_case,
    get_case,
    list_cases,
)


# This repo's .env sets DATABASE_URL, which would route these unit tests through
# Postgres. Pin it empty so the in-memory path is exercised deterministically.
# DB persistence is covered by TestHomeOSCaseStorePersistence + the e2e spec.
@patch.dict(os.environ, {"DATABASE_URL": ""}, clear=False)
class TestHomeOSCaseStore(unittest.TestCase):
    def setUp(self):
        from app.homeos import case_store
        case_store._cases.clear()

    def test_create_case_returns_case_with_id(self):
        case = create_case("Family looking for 4 room under 800k.")
        self.assertIsNotNone(case["case_id"])
        self.assertEqual(case["profile_text"], "Family looking for 4 room under 800k.")
        self.assertEqual(case["status"], "running")
        self.assertEqual(case["pipeline"], [])
        self.assertEqual(case["shortlist"], [])
        self.assertEqual(case["conversation"], [])

    def test_create_case_defaults_user_id_zero(self):
        case = create_case("anon profile")
        self.assertEqual(case["user_id"], 0)

    def test_create_case_stores_user_id(self):
        case = create_case("profile", user_id=42)
        self.assertEqual(case["user_id"], 42)
        self.assertEqual(get_case(case["case_id"])["user_id"], 42)

    def test_get_case_returns_same_case(self):
        case = create_case("test profile")
        fetched = get_case(case["case_id"])
        self.assertEqual(fetched["case_id"], case["case_id"])

    def test_get_case_returns_none_for_unknown_id(self):
        self.assertIsNone(get_case("nonexistent-id"))

    def test_list_cases_returns_newest_first(self):
        c1 = create_case("first")
        c2 = create_case("second")
        cases = list_cases()
        self.assertEqual(cases[0]["case_id"], c2["case_id"])
        self.assertEqual(cases[1]["case_id"], c1["case_id"])

    def test_list_cases_filters_by_user(self):
        mine = create_case("mine", user_id=1)
        _theirs = create_case("theirs", user_id=2)
        cases = list_cases(user_id=1)
        self.assertEqual([c["case_id"] for c in cases], [mine["case_id"]])

    def test_append_event_adds_to_pipeline(self):
        case = create_case("test profile")
        event = {"event": "agent_start", "agent": "market", "block_id": 1}
        append_event(case["case_id"], event)
        updated = get_case(case["case_id"])
        self.assertEqual(len(updated["pipeline"]), 1)
        self.assertEqual(updated["pipeline"][0]["agent"], "market")

    def test_append_message_adds_to_conversation(self):
        case = create_case("test profile")
        append_message(case["case_id"], "user", "Why Bishan?")
        append_message(case["case_id"], "assistant", "Because of the schools.")
        updated = get_case(case["case_id"])
        self.assertEqual(len(updated["conversation"]), 2)
        self.assertEqual(updated["conversation"][0]["role"], "user")
        self.assertEqual(updated["conversation"][1]["content"], "Because of the schools.")

    def test_persistence_disabled_when_no_database_url(self):
        # With DATABASE_URL empty (pinned above), mutations must never open a
        # DB connection — _save short-circuits before touching Postgres.
        from app.homeos import case_store
        with patch.object(case_store, "_conn") as conn:
            create_case("no db here", user_id=7)
            append_event(create_case("c2", user_id=7)["case_id"], {"event": "x"})
            conn.assert_not_called()


def _seed_user(email: str) -> int:
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


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "needs Postgres")
class TestHomeOSCaseStorePersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # homeos_cases.user_id has a FK to users(id); seed real owners.
        cls.user_a = _seed_user("case_store_persist_a@test.local")
        cls.user_b = _seed_user("case_store_persist_b@test.local")

    def setUp(self):
        from app.homeos import case_store
        case_store._cases.clear()
        self._delete(self.user_a)
        self._delete(self.user_b)

    def tearDown(self):
        self._delete(self.user_a)
        self._delete(self.user_b)

    @staticmethod
    def _delete(user_id: int) -> None:
        from app.db.session import get_engine
        conn = get_engine().raw_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM homeos_cases WHERE user_id = %s", (user_id,))
            conn.commit()
        finally:
            conn.close()

    def test_case_survives_cache_eviction(self):
        from app.homeos import case_store
        case = create_case("persist me", user_id=self.user_a)
        append_event(case["case_id"], {"event": "agent_done", "agent": "market", "block_id": 1})
        # Evict the in-memory copy → get_case must rehydrate from Postgres.
        case_store._cases.clear()
        reloaded = get_case(case["case_id"])
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded["user_id"], self.user_a)
        self.assertEqual(len(reloaded["pipeline"]), 1)
        self.assertEqual(reloaded["pipeline"][0]["agent"], "market")

    def test_list_cases_user_scoped_from_db(self):
        from app.homeos import case_store
        mine = create_case("mine", user_id=self.user_a)
        create_case("theirs", user_id=self.user_b)
        case_store._cases.clear()
        scoped = list_cases(user_id=self.user_a)
        ids = [c["case_id"] for c in scoped]
        self.assertIn(mine["case_id"], ids)
        self.assertTrue(all(c["user_id"] == self.user_a for c in scoped))


if __name__ == "__main__":
    unittest.main()
