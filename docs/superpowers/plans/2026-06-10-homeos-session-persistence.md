# HomeOS Session Persistence (Per-User) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist HomeOS investigation cases to Postgres, scoped per authenticated user, so a user's past sessions survive server restarts, load into the sidebar on login, can be reopened to view the exact same output, and the **+** button opens a *blank* new session instead of auto-submitting a default prompt.

**Architecture:** `case_store.py` becomes a **write-through** store: it keeps the existing in-memory dict as a live cache but also upserts each case (as a JSONB blob plus denormalized `user_id`/`status`/`profile_text` columns) into a new `homeos_cases` table on every mutation. Persistence is **best-effort and opt-in** — when `DATABASE_URL` is unset (unit tests, mock mode) every DB call is skipped and behavior is byte-for-byte identical to today, so no existing test changes. `user_id` flows from the JWT (`require_subscribed` → `CurrentUser.user_id`) through the routes into `investigate_stream` → `create_case`. The frontend already renders the right panel from `activeCase.pipeline` + `activeCase.shortlist` (PipelinePanel.tsx:114,121), so "view the same output" is achieved purely by fetching the full case (`getCase`) on selection and dropping it into existing state.

**Tech Stack:** FastAPI, psycopg 3 (via SQLAlchemy engine `raw_connection()`), Postgres/PostGIS, plain ordered `.sql` migrations (`app/db/migrate.py`), React 18 + TypeScript (plain `useState`, no store), Vite.

---

## Background: exactly what is broken today

Verified against the current code:

1. **Cases are in-memory only and global.** `backend/app/homeos/case_store.py` stores cases in a module-level `_cases: dict`. They die on restart and are **not** scoped to a user — `GET /homeos/cases` returns *every* user's cases (`main.py:317-329`).
2. **`investigate_stream` never receives a user.** `pipeline.py:741` `create_case(profile_text)` — no `user_id`. The route has `_user` (`main.py:300-304`) but discards it.
3. **The frontend never loads past cases.** There is no mount-time `getCases()` call in `App.tsx`. The sidebar (`CasesPanel.tsx`) only ever shows cases created in the current tab session.
4. **Selecting an old case shows nothing.** `handleSelectCase` (`App.tsx:342-346`) sets `activeCaseId` but never calls `getCase()`, so `activeCaseFull` is not populated → the right panel is blank/stale. This is the "go back to old cases and view the same output" gap.
5. **The "+" button auto-prompts.** `CasesPanel.tsx:303-306` — the **+** button calls `onNewCase(DEFAULT_PROFILE)`, immediately starting an investigation with the hard-coded string `"Family looking for 4 room under 800k near primary schools and MRT."`. This is the "currently it auto prompts" behavior the user wants gone.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `backend/tests/e2e/test_session_persistence_e2e.py` | Outside-in acceptance spec (the driver) | **Created — RED** |
| `backend/app/db/migrations/sql/0010_homeos_cases.sql` | `homeos_cases` table + index | **Create** |
| `backend/tests/test_migrations_sql.py` | Assert table exists in migration SQL | Modify (add 1 test) |
| `backend/app/homeos/case_store.py` | Write-through persistence + user scoping | Modify (rewrite) |
| `backend/tests/test_homeos_case_store.py` | user_id + per-user list + persistence round-trip | Modify (add tests) |
| `backend/app/homeos/pipeline.py` | Thread `user_id` into `create_case` | Modify (`investigate_stream` sig + 1 call) |
| `backend/app/api/main.py` | Pass `user_id`; user-scoped list; ownership 404s | Modify (4 routes) |
| `frontend/src/App.tsx` | Load cases on mount; select loads full case; blank new-session handler | Modify |
| `frontend/src/components/CasesPanel.tsx` | **+** opens blank session via `onNewSession` | Modify |

No new frontend types or API client functions are required — `getCases`/`getCase` already exist (`api.ts:285-291`) and already send auth headers.

---

## Task 0: End-to-end acceptance spec (the outside-in driver) — ALREADY WRITTEN

**Files:**
- Created: `backend/tests/e2e/test_session_persistence_e2e.py`

This spec is the executable definition of done. It drives the whole feature through the real HTTP API against the real Postgres `homeos_cases` table, simulating two distinct users via `app.dependency_overrides[require_subscribed]` (the repo's `.env` sets `AUTH_REQUIRED=false`, which otherwise collapses every caller to user 0). Block data comes from an in-memory `build_seeded_repo` so it does not depend on a seeded PostGIS; persistence still exercises real Postgres because `case_store` opens its own connection. It skips automatically when `DATABASE_URL` is unset/unreachable.

Three behaviors are asserted:
1. `test_investigation_persists_under_the_owner` — owner can list + open their case with its pipeline. **(already green: the in-memory store satisfies this today.)**
2. `test_cases_are_scoped_per_user` — user B cannot list or open user A's case (404, existence not leaked). **(RED until Tasks 2-3.)**
3. `test_case_survives_server_restart` — after `case_store._cases.clear()`, reopening the case via the API returns 200 with the same pipeline + shortlist. **(RED until Tasks 1-2.)**

- [ ] **Step 1: Confirm the current RED baseline**

Run: `cd backend && .venv/bin/python -m pytest tests/e2e/test_session_persistence_e2e.py -v`
Expected (before implementing Tasks 1-3): `1 passed, 2 failed` — `test_cases_are_scoped_per_user` (user B sees A's case) and `test_case_survives_server_restart` (404 after cache clear). If it reports `3 skipped`, your DB is unreachable — start it (`docker compose up -d` / `python setup.py --run`) and apply migrations (`python -m app.db.migrate`).

- [ ] **Step 2: Do NOT commit yet**

Leave the spec red. It turns green incrementally as Tasks 1-3 land; the final check is in Task 3 Step 9. Commit it together with Task 1 (it is the acceptance test for the whole backend change).

---

## Task 1: Database migration for `homeos_cases`

**Files:**
- Create: `backend/app/db/migrations/sql/0010_homeos_cases.sql`
- Test: `backend/tests/test_migrations_sql.py` (add one method)

The migration runner (`app/db/migrate.py`) discovers `*.sql` files sorted by name and applies any not in `schema_migrations`. `test_migrations_sql.py` concatenates every `.sql` file and asserts invariants without a DB — so we TDD the migration by asserting the table appears in the SQL text.

- [ ] **Step 1: Write the failing test**

Add this method inside `class TestMigrationsSql` in `backend/tests/test_migrations_sql.py` (after `test_postgis_extension_enabled`):

```python
    def test_homeos_cases_table_created(self):
        self.assertRegex(
            self.sql,
            r"CREATE TABLE IF NOT EXISTS homeos_cases\s*\(",
            "missing CREATE TABLE homeos_cases",
        )
        # Must be user-scoped and JSONB-backed.
        block = self.sql[self.sql.index("homeos_cases"):]
        self.assertRegex(block, r"user_id\s+INTEGER", "homeos_cases needs user_id INTEGER")
        self.assertRegex(block, r"data\s+JSONB", "homeos_cases needs data JSONB")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_migrations_sql.py::TestMigrationsSql::test_homeos_cases_table_created -v`
Expected: FAIL with "missing CREATE TABLE homeos_cases".

- [ ] **Step 3: Create the migration**

Create `backend/app/db/migrations/sql/0010_homeos_cases.sql`:

```sql
-- 0010_homeos_cases: persisted HomeOS investigation cases, scoped per user.
-- The full case object (avatar, pipeline events, shortlist, conversation,
-- search state) is stored as a JSONB blob in `data`. The scalar columns are
-- denormalized copies used for cheap list queries and ownership checks.
CREATE TABLE IF NOT EXISTS homeos_cases (
    case_id       TEXT PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_text  TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'running',
    data          JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- List "my cases, newest first" hits this index.
CREATE INDEX IF NOT EXISTS homeos_cases_user_idx
    ON homeos_cases (user_id, created_at DESC);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_migrations_sql.py -v`
Expected: PASS (all migration tests, including the new one).

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/migrations/sql/0010_homeos_cases.sql backend/tests/test_migrations_sql.py backend/tests/e2e/test_session_persistence_e2e.py
git commit -m "feat(homeos): add homeos_cases migration + e2e session-persistence spec"
```

> The e2e acceptance spec (Task 0) is committed here alongside the migration. It stays red until Tasks 2-3 complete.

---

## Task 2: Write-through, user-scoped `case_store`

**Files:**
- Modify: `backend/app/homeos/case_store.py`
- Test: `backend/tests/test_homeos_case_store.py`

The new store keeps the in-memory `_cases` cache (so existing behavior/tests are unchanged when no DB), adds a `user_id` field to every case, persists through to `homeos_cases` on every mutation when `DATABASE_URL` is set, and can rehydrate a case from the DB on `get_case` miss. All DB access is wrapped so a failure logs and falls back to memory — a demo must never crash because Postgres hiccupped.

### 2a — Unit tests (run without a DB; persistence path disabled)

- [ ] **Step 1: Write the failing tests**

Replace the imports at the top of `backend/tests/test_homeos_case_store.py` and append the new tests. Final file:

```python
import os
import unittest
from unittest.mock import patch

from app.homeos.case_store import (
    append_event,
    append_message,
    create_case,
    get_case,
    list_cases,
)


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

    @patch.dict(os.environ, {}, clear=False)
    def test_persistence_disabled_when_no_database_url(self):
        # With DATABASE_URL unset, mutations must never touch the DB layer.
        from app.homeos import case_store
        os.environ.pop("DATABASE_URL", None)
        with patch.object(case_store, "_save") as save:
            create_case("no db here", user_id=7)
            save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_homeos_case_store.py -v`
Expected: FAIL — `create_case() got an unexpected keyword argument 'user_id'` (and `_save` does not exist yet).

- [ ] **Step 3: Rewrite `case_store.py`**

Replace the entire contents of `backend/app/homeos/case_store.py` with:

```python
"""Per-user Case store for HomeOS investigations.

In-memory dict (`_cases`) is the live working cache. When DATABASE_URL is set,
every mutation is *also* written through to the `homeos_cases` table so cases
survive restarts and can be listed/reopened by their owner. When DATABASE_URL
is unset (unit tests, mock mode) the DB layer is skipped entirely and this
behaves as a pure in-memory store.

Write-through is best-effort: a DB error is logged and swallowed so a live
investigation never crashes on a transient Postgres issue.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_cases: dict[str, dict[str, Any]] = {}


# ── Persistence layer (best-effort, opt-in via DATABASE_URL) ──────────────────

def _db_enabled() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def _conn():
    """psycopg connection from the shared SQLAlchemy pool (same as auth.py)."""
    from app.db.session import get_engine
    return get_engine().raw_connection()


def _save(case: dict[str, Any]) -> None:
    """Upsert the full case JSON + denormalized columns. Never raises."""
    if not _db_enabled():
        return
    try:
        conn = _conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO homeos_cases
                        (case_id, user_id, profile_text, status, data, updated_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (case_id) DO UPDATE SET
                        profile_text = EXCLUDED.profile_text,
                        status       = EXCLUDED.status,
                        data         = EXCLUDED.data,
                        updated_at   = NOW()
                    """,
                    (
                        case["case_id"],
                        int(case.get("user_id", 0)),
                        case.get("profile_text", ""),
                        case.get("status", "running"),
                        json.dumps(case),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive, demo must not crash
        logger.warning("homeos_cases save failed for %s: %s", case.get("case_id"), exc)


def _load(case_id: str) -> dict[str, Any] | None:
    if not _db_enabled():
        return None
    try:
        conn = _conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM homeos_cases WHERE case_id = %s", (case_id,))
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover
        logger.warning("homeos_cases load failed for %s: %s", case_id, exc)
        return None
    if not row:
        return None
    data = row[0]
    return data if isinstance(data, dict) else json.loads(data)


def _load_for_user(user_id: int) -> list[dict[str, Any]]:
    if not _db_enabled():
        return []
    try:
        conn = _conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data FROM homeos_cases WHERE user_id = %s "
                    "ORDER BY created_at DESC",
                    (user_id,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover
        logger.warning("homeos_cases list failed for user %s: %s", user_id, exc)
        return []
    out: list[dict[str, Any]] = []
    for (data,) in rows:
        out.append(data if isinstance(data, dict) else json.loads(data))
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def create_case(profile_text: str, user_id: int = 0) -> dict[str, Any]:
    case_id = str(uuid.uuid4())
    case: dict[str, Any] = {
        "case_id": case_id,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile_text": profile_text,
        "avatar": None,
        "pipeline": [],
        "shortlist": [],
        "conversation": [],
        "status": "running",
        "search_prefs": {},
        "candidate_ids": [],
    }
    _cases[case_id] = case
    _save(case)
    return case


def get_case(case_id: str) -> dict[str, Any] | None:
    case = _cases.get(case_id)
    if case is not None:
        return case
    loaded = _load(case_id)
    if loaded is not None:
        _cases[case_id] = loaded  # re-warm the cache
    return loaded


def list_cases(user_id: int | None = None) -> list[dict[str, Any]]:
    if _db_enabled() and user_id is not None:
        return _load_for_user(user_id)
    cases = list(_cases.values())
    if user_id is not None:
        cases = [c for c in cases if c.get("user_id") == user_id]
    return sorted(cases, key=lambda c: c["created_at"], reverse=True)


def append_event(case_id: str, event: dict[str, Any]) -> None:
    case = _cases.get(case_id)
    if case is not None:
        case["pipeline"].append(event)
        _save(case)


def append_message(case_id: str, role: str, content: str) -> None:
    case = _cases.get(case_id)
    if case is not None:
        case["conversation"].append({"role": role, "content": content})
        _save(case)


def set_avatar(case_id: str, avatar: dict[str, Any]) -> None:
    case = _cases.get(case_id)
    if case is not None:
        case["avatar"] = avatar
        _save(case)


def set_shortlist(case_id: str, shortlist: list[dict[str, Any]]) -> None:
    case = _cases.get(case_id)
    if case is not None:
        case["shortlist"] = shortlist
        _save(case)


def set_status(case_id: str, status: str) -> None:
    case = _cases.get(case_id)
    if case is not None:
        case["status"] = status
        _save(case)


def set_search_state(case_id: str, prefs: dict[str, Any], candidate_ids: list[int]) -> None:
    case = _cases.get(case_id)
    if case is not None:
        case["search_prefs"] = prefs
        case["candidate_ids"] = candidate_ids
        _save(case)
```

> **Note on write volume:** `append_event` persists on every SSE event (~80 writes per investigation at the 5-block threshold). That is fine for the demo and gives correct mid-stream recovery. If it ever becomes a bottleneck, batch by persisting only on `agent_done`/`case_done` — out of scope here.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_homeos_case_store.py -v`
Expected: PASS (all 11 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/homeos/case_store.py backend/tests/test_homeos_case_store.py
git commit -m "feat(homeos): write-through DB persistence and user scoping in case_store"
```

### 2b — DB round-trip integration test (skips without DATABASE_URL)

- [ ] **Step 6: Write the DB-backed round-trip test**

Append to `backend/tests/test_homeos_case_store.py` (after the unit `TestHomeOSCaseStore` class):

```python
@unittest.skipUnless(os.environ.get("DATABASE_URL"), "needs Postgres")
class TestHomeOSCaseStorePersistence(unittest.TestCase):
    def setUp(self):
        from app.homeos import case_store
        case_store._cases.clear()

    def test_case_survives_cache_eviction(self):
        from app.homeos import case_store
        case = create_case("persist me", user_id=99)
        append_event(case["case_id"], {"event": "agent_done", "agent": "market", "block_id": 1})
        # Evict the in-memory copy → get_case must rehydrate from Postgres.
        case_store._cases.clear()
        reloaded = get_case(case["case_id"])
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded["user_id"], 99)
        self.assertEqual(len(reloaded["pipeline"]), 1)
        self.assertEqual(reloaded["pipeline"][0]["agent"], "market")

    def test_list_cases_user_scoped_from_db(self):
        from app.homeos import case_store
        mine = create_case("mine", user_id=1001)
        create_case("theirs", user_id=1002)
        case_store._cases.clear()
        ids = [c["case_id"] for c in list_cases(user_id=1001)]
        self.assertIn(mine["case_id"], ids)
        self.assertTrue(all(c["user_id"] == 1001 for c in list_cases(user_id=1001)))
```

- [ ] **Step 7: Run it (with a live DB if available)**

Run: `cd backend && DATABASE_URL=$DATABASE_URL .venv/bin/python -m pytest tests/test_homeos_case_store.py::TestHomeOSCaseStorePersistence -v`
Expected: PASS against a migrated DB, or `SKIPPED` when `DATABASE_URL` is unset.
(If running against a fresh DB, apply migrations first: `cd backend && python -m app.db.migrate`.)

- [ ] **Step 8: Commit**

```bash
git add backend/tests/test_homeos_case_store.py
git commit -m "test(homeos): DB round-trip + user-scoped list persistence tests"
```

---

## Task 3: Thread `user_id` through the pipeline and routes

**Files:**
- Modify: `backend/app/homeos/pipeline.py:741-747` (`investigate_stream` signature + `create_case` call)
- Modify: `backend/app/api/main.py` (`/investigate-stream`, `/cases`, `/cases/{id}`, `/cases/{id}/chat`, `/cases/{id}/refine`)
- Test: `backend/tests/test_homeos_stream.py` (add a signature/ownership unit test)

### 3a — Pipeline accepts `user_id`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_homeos_stream.py` (a focused test that does not need an LLM — it only checks the new case is tagged with the user, using mock mode):

```python
import os
import unittest
from unittest.mock import patch


class TestInvestigateStreamUserScoping(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, {"HOMEOS_AGENT_MODE": "mock", "DATABASE_URL": ""}, clear=False)
    async def test_investigate_stream_tags_case_with_user(self):
        from app.homeos.wiring import setup as homeos_setup
        from app.homeos import case_store
        from app.homeos.pipeline import investigate_stream
        from app.repository import get_repository  # adjust import to the project's repo factory

        homeos_setup()
        case_store._cases.clear()
        repo = get_repository()

        case_id = None
        async for event in investigate_stream(repo, "Family wanting 4 room near MRT.", user_id=555):
            if event.get("case_id"):
                case_id = event["case_id"]
        # The created case must carry the caller's user_id.
        any_case = next(iter(case_store._cases.values()))
        self.assertEqual(any_case["user_id"], 555)
```

> If `get_repository` lives elsewhere, locate it with `grep -rn "def get_repository" backend/app` and fix the import. The point of the test is only the `user_id=555` propagation.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_homeos_stream.py::TestInvestigateStreamUserScoping -v`
Expected: FAIL — `investigate_stream() got an unexpected keyword argument 'user_id'`.

- [ ] **Step 3: Add `user_id` to `investigate_stream`**

In `backend/app/homeos/pipeline.py`, change the signature at line 741 and the `create_case` call at line 746:

```python
async def investigate_stream(
    repo: Repository,
    profile_text: str,
    limit: int = 5,
    user_id: int = 0,
) -> AsyncGenerator[dict, None]:
    case = homeos_case_store.create_case(profile_text, user_id=user_id)
    case_id = case["case_id"]
```

(Leave the rest of the function unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_homeos_stream.py::TestInvestigateStreamUserScoping -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/homeos/pipeline.py backend/tests/test_homeos_stream.py
git commit -m "feat(homeos): investigate_stream accepts user_id and tags the case"
```

### 3b — Routes pass the user and enforce ownership

- [ ] **Step 6: Update the routes**

In `backend/app/api/main.py`:

**(a)** `/homeos/investigate-stream` (line 306-308) — pass the user id:

```python
    async def event_gen():
        async for event in investigate_stream(
            repo, req.profile_text, req.limit, user_id=_user.user_id
        ):
            yield f"data: {json.dumps(event)}\n\n"
```

**(b)** `/homeos/cases` (line 318-319) — scope the list to the caller:

```python
@app.get("/homeos/cases")
def homeos_list_cases(_user=Depends(require_subscribed)):
    cases = homeos_case_store.list_cases(user_id=_user.user_id)
```

(leave the list-comprehension return shape below it unchanged.)

**(c)** `/homeos/cases/{case_id}` (line 332-337) — 404 on missing *or* not-owned (404, not 403, so case existence isn't leaked):

```python
@app.get("/homeos/cases/{case_id}")
def homeos_get_case(case_id: str, _user=Depends(require_subscribed)):
    case = homeos_case_store.get_case(case_id)
    if case is None or case.get("user_id", 0) != _user.user_id:
        raise HTTPException(status_code=404, detail="case not found")
    return case
```

**(d)** `/homeos/cases/{case_id}/chat` (line 343-344) and `/homeos/cases/{case_id}/refine` (line 365-367) — replace the existence-only guard with the same ownership guard. For chat:

```python
    case = homeos_case_store.get_case(case_id)
    if case is None or case.get("user_id", 0) != _user.user_id:
        raise HTTPException(status_code=404, detail="case not found")
```

For refine, the variable is already named `case`; change its guard line to:

```python
    case = homeos_case_store.get_case(case_id)
    if case is None or case.get("user_id", 0) != _user.user_id:
        raise HTTPException(status_code=404, detail="case not found")
```

- [ ] **Step 7: Run the backend HomeOS suite to confirm no regressions**

Run: `cd backend && .venv/bin/python -m pytest tests/test_homeos_case_store.py tests/test_homeos_stream.py tests/test_homeos_stream_api.py -v`
Expected: PASS, except the **known baseline failures on main** (`test_homeos_service::test_parse_family_profile` + 3× `test_homeos_stream` clarifying-question tests) which are pre-existing and NOT caused by this change. Confirm any failures match that list exactly.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/main.py
git commit -m "feat(homeos): scope case routes to the authenticated user with ownership checks"
```

- [ ] **Step 9: Turn the Task 0 acceptance spec GREEN**

Run: `cd backend && .venv/bin/python -m pytest tests/e2e/test_session_persistence_e2e.py -v`
Expected: `3 passed`. All three behaviors — owner persistence, per-user scoping (404 for others), and survives-restart rehydration from Postgres — now hold end-to-end. If any test is still red, the backend feature is incomplete; do not proceed to the frontend tasks until this is green.

---

## Task 4: Frontend — load the user's past cases on mount

**Files:**
- Modify: `frontend/src/App.tsx` (add a mount effect near the other auth effects, ~line 119)

When the user is authenticated and subscribed (AI mode is gated on subscription, and `getCases` requires it), fetch their cases once and populate the sidebar.

- [ ] **Step 1: Add the imports (if missing)**

Confirm `getCases` is imported in `App.tsx`:

Run: `grep -n "getCases\|getCase\b" frontend/src/App.tsx`
If absent, add `getCases, getCase` to the existing `from "./lib/api"` import block (the one already importing `investigateStream, refineStream, chatInCase`).

- [ ] **Step 2: Add the mount effect**

Insert this effect immediately after the Stripe-redirect `useEffect` (after `App.tsx:136`), so it runs once on mount:

```tsx
  // Load this user's persisted cases into the sidebar on mount.
  useEffect(() => {
    if (!authUser?.is_subscribed) return;
    getCases()
      .then((loaded) => setCases(loaded))
      .catch(() => {/* unauthenticated / 402 — leave sidebar empty */});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authUser?.is_subscribed]);
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 4: Manual smoke (optional but recommended)**

Start the app (`python setup.py --run` from repo root per project setup), log in as a subscribed user who has past cases, switch to AI mode, and confirm the case dropdown in the left panel lists prior investigations.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): load persisted HomeOS cases into the sidebar on mount"
```

---

## Task 5: Frontend — reopening a case shows the same output

**Files:**
- Modify: `frontend/src/App.tsx:342-346` (`handleSelectCase`)

`handleSelectCase` currently only sets `activeCaseId`. Make it fetch the full case and load it into the exact state the panels render from (`activeCaseFull`, `shortlistIds`, `hasAiMapFilter`), with `streamingEvents` cleared. PipelinePanel reads `activeCase.pipeline` (PipelinePanel.tsx:121) and `activeCase.shortlist` (PipelinePanel.tsx:114), so this reproduces the original output verbatim.

- [ ] **Step 1: Replace `handleSelectCase`**

Replace the existing `handleSelectCase` (`App.tsx:342-346`) with:

```tsx
  const handleSelectCase = useCallback(async (caseId: string) => {
    setActiveCaseId(caseId);
    setRightPanel("pipeline");
    setAiSelectedBlockId(null);
    setStreamingEvents([]);
    setFramedCaseId(null);

    // A case still mid-stream in this tab has no persisted snapshot to fetch.
    if (caseId.startsWith("pending-")) return;

    try {
      const full = await getCase(caseId);
      setActiveCaseFull(full);
      const ids = full.shortlist.map((row) => row.block_id);
      setShortlistIds(ids);
      setHasAiMapFilter(full.status === "done" && ids.length > 0);
    } catch {
      // 404 / not owned — clear the stale view.
      setActiveCaseFull(null);
      setShortlistIds([]);
      setHasAiMapFilter(false);
    }
  }, []);
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors. (`getCase` returns `Promise<HomeOSCase>`, `HomeOSShortlistRow.block_id` is `number` — types.ts.)

- [ ] **Step 3: Manual smoke**

Run an investigation to completion, click **+** logic aside, open the dropdown and reselect that finished case: the pipeline narratives, shortlist rows, and the map's highlighted blocks must reappear identically. Reselect a `refining` case: the clarifying question and chat history must reappear.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): reopening a case loads its full pipeline + shortlist (same output)"
```

---

## Task 6: Frontend — the "+" button opens a blank session

**Files:**
- Modify: `frontend/src/App.tsx` (add `handleNewSession`; pass as prop)
- Modify: `frontend/src/components/CasesPanel.tsx` (Props + the **+** button onClick)

Today **+** calls `onNewCase(DEFAULT_PROFILE)` and immediately starts an investigation. New behavior: **+** clears state to a blank session; the user types their own requirements; `handleSubmit` (already in CasesPanel.tsx:235-238) starts the investigation when there is no active case.

- [ ] **Step 1: Add `handleNewSession` in App.tsx**

Insert after `handleNewCase` (after `App.tsx:315`):

```tsx
  const handleNewSession = useCallback(() => {
    setActiveCaseId(null);
    setActiveCaseFull(null);
    setStreamingEvents([]);
    setShortlistIds([]);
    setHasAiMapFilter(false);
    setAiSelectedBlockId(null);
    setFramedCaseId(null);
    setRightPanel("pipeline");
  }, []);
```

- [ ] **Step 2: Pass it to CasesPanel**

In the `<CasesPanel ... />` JSX (`App.tsx:657-667`), add the prop right after `onNewCase={handleNewCase}`:

```tsx
            onNewCase={handleNewCase}
            onNewSession={handleNewSession}
```

- [ ] **Step 3: Add `onNewSession` to CasesPanel Props**

In `frontend/src/components/CasesPanel.tsx`, add to the `Props` interface (after `onNewCase`, line 135):

```tsx
  onNewCase: (profileText: string) => void;
  onNewSession: () => void;
```

And add it to the destructured params (after `onNewCase,`, line 183):

```tsx
  onNewCase,
  onNewSession,
```

- [ ] **Step 4: Rewire the "+" button**

Replace the **+** button onClick (`CasesPanel.tsx:303-306`):

```tsx
          onClick={() => {
            setShowDropdown(false);
            onNewSession();
          }}
```

`DEFAULT_PROFILE` (CasesPanel.tsx:172) is now unused by the button. Keep it only if it is referenced elsewhere; otherwise delete the constant to avoid an unused-variable lint error:

Run: `grep -n "DEFAULT_PROFILE" frontend/src/components/CasesPanel.tsx`
If the only remaining reference is its declaration, delete lines 172-173.

- [ ] **Step 5: Type-check and lint**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors (no unused `onNewSession`, no unused `DEFAULT_PROFILE`).

- [ ] **Step 6: Manual smoke**

Click **+**: the chat panel resets to the empty-state copy ("Start a new investigation by typing your requirements below…", CasesPanel.tsx:317-318), the input placeholder is "Describe your household, budget, commute, schools…", and **no** investigation starts until you type and submit. Submitting then starts a real investigation (which persists, owned by you).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/CasesPanel.tsx
git commit -m "feat(frontend): + button opens a blank session instead of auto-submitting a default prompt"
```

---

## Final verification

- [ ] **Acceptance spec:** `cd backend && .venv/bin/python -m pytest tests/e2e/test_session_persistence_e2e.py -v` — `3 passed` (or `3 skipped` only if no DB).
- [ ] **Backend:** `cd backend && .venv/bin/python -m pytest tests/ -q` — only the documented baseline failures remain (test_homeos_service::test_parse_family_profile + 3× test_homeos_stream clarifying-question tests). Everything in this plan's scope passes.
- [ ] **Frontend:** `cd frontend && npx tsc --noEmit && npm run build` — clean.
- [ ] **End-to-end (manual, with a DB):** apply migrations (`cd backend && python -m app.db.migrate`), run two investigations as user A, **restart the backend**, reload the app: both cases still appear in user A's sidebar and reopen with identical output. Log in as user B: user A's cases are absent (user-scoped). Click **+**: a blank session, no auto-prompt.

---

## Self-Review (performed against the request)

**Spec coverage:**
- "sessions to persist" → Task 1 (table) + Task 2 (write-through store).
- "store session per users" → `user_id` column + Task 2 scoping + Task 3 routes (list scoped, ownership 404s).
- "start new session with the + button … currently it auto prompts" → Task 6 (blank-session handler, **+** no longer submits `DEFAULT_PROFILE`).
- "go back to old cases and view the same output" → Task 4 (load on mount) + Task 5 (`getCase` → `activeCaseFull` + `shortlistIds`, rendered by existing PipelinePanel from `activeCase.pipeline`/`activeCase.shortlist`).

**Placeholder scan:** every code step contains full code; no TBD/"add error handling"/"similar to". DB-error handling is shown explicitly (try/except + logger). The one import to verify (`get_repository` in Task 3a) is flagged with the exact grep to resolve it.

**Type consistency:** backend `create_case(profile_text, user_id=0)` matches every call site (`pipeline.py`, tests). `list_cases(user_id=None)` is back-compatible with the existing no-arg call removed in favor of the scoped call in Task 3b. Frontend `onNewSession: () => void` is declared in Props, destructured, passed from App, and invoked by the button. `getCase` → `HomeOSCase`; `HomeOSShortlistRow.block_id: number` feeds `shortlistIds: number[]`. `handleSelectCase` becomes `async` but its only consumer is `onSelectCase: (caseId: string) => void` — an async function is assignable to a `void`-returning prop.

**Known-failure guard:** Task 3b Step 7 and Final verification both pin the expectation to the documented baseline failures so a reviewer doesn't mistake them for regressions.
