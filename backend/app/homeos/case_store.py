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
    # In-memory cache is the authoritative live source within this process;
    # the DB adds cases persisted by earlier runs. Merge both, preferring the
    # in-memory copy (fresher) on case_id collisions.
    mem = list(_cases.values())
    if user_id is not None:
        mem = [c for c in mem if c.get("user_id") == user_id]
    if _db_enabled() and user_id is not None:
        seen = {c["case_id"] for c in mem}
        mem += [c for c in _load_for_user(user_id) if c["case_id"] not in seen]
    return sorted(mem, key=lambda c: c["created_at"], reverse=True)


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
