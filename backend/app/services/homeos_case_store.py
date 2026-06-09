"""In-memory Case store for HomeOS investigations.

Cases are stored for the lifetime of the server process only.
No database — sufficient for hackathon demo.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

_cases: dict[str, dict[str, Any]] = {}


def create_case(profile_text: str) -> dict[str, Any]:
    case_id = str(uuid.uuid4())
    case: dict[str, Any] = {
        "case_id": case_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile_text": profile_text,
        "avatar": None,
        "pipeline": [],
        "shortlist": [],
        "conversation": [],
        "status": "running",
    }
    _cases[case_id] = case
    return case


def get_case(case_id: str) -> dict[str, Any] | None:
    return _cases.get(case_id)


def list_cases() -> list[dict[str, Any]]:
    return sorted(_cases.values(), key=lambda c: c["created_at"], reverse=True)


def append_event(case_id: str, event: dict[str, Any]) -> None:
    if case_id in _cases:
        _cases[case_id]["pipeline"].append(event)


def append_message(case_id: str, role: str, content: str) -> None:
    if case_id in _cases:
        _cases[case_id]["conversation"].append({"role": role, "content": content})


def set_avatar(case_id: str, avatar: dict[str, Any]) -> None:
    if case_id in _cases:
        _cases[case_id]["avatar"] = avatar


def set_shortlist(case_id: str, shortlist: list[dict[str, Any]]) -> None:
    if case_id in _cases:
        _cases[case_id]["shortlist"] = shortlist


def set_status(case_id: str, status: str) -> None:
    if case_id in _cases:
        _cases[case_id]["status"] = status
