"""Saved user state — preferences + locations CRUD.

Backs the logged-in experience (Feature 1): a user's saved locations and
preferences so they don't re-key the same info. Gated by require_user at the
route layer; anonymous users keep state client-side until they log in.

Small per-user reads/writes over PostGIS via SQLAlchemy text() (same style as
the other services).
"""
from __future__ import annotations

from typing import Any

# Whitelisted preference columns (also the upsert column set).
PREF_FIELDS = (
    "preferred_property_modes", "last_search_mode", "commute_weight",
    "lifestyle_weight", "affordability_weight", "schools_weight", "mrt_weight",
    "future_mrt_weight", "max_budget", "preferred_towns", "preferred_flat_types",
    "preferred_private_property_types",
)
LOCATION_TYPES = {"home", "work", "school", "partner", "family", "custom"}


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


# ── preferences ───────────────────────────────────────────────────────────────

def get_preferences(engine, user_id: int) -> dict | None:
    from sqlalchemy import text
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM user_preferences WHERE user_id = :u"),
                           {"u": user_id}).mappings().first()
    if row is None:
        return None
    out = {k: _iso(v) for k, v in dict(row).items()}
    return out


def upsert_preferences(engine, user_id: int, data: dict[str, Any]) -> dict:
    """Insert or update the caller's preferences. Unknown keys are ignored;
    metadata_json is merged-replaced wholesale if provided."""
    from sqlalchemy import text
    fields = {k: data[k] for k in PREF_FIELDS if k in data}
    metadata = data.get("metadata_json")

    cols = ["user_id", *fields.keys()]
    if metadata is not None:
        cols.append("metadata_json")
    placeholders = ", ".join(f":{c}" for c in cols)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "user_id")
    updates = (updates + ", " if updates else "") + "updated_at = NOW()"

    params: dict[str, Any] = {"user_id": user_id, **fields}
    if metadata is not None:
        import json
        params["metadata_json"] = json.dumps(metadata)

    sql = (f"INSERT INTO user_preferences ({', '.join(cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT (user_id) DO UPDATE SET {updates}")
    with engine.begin() as conn:
        conn.execute(text(sql), params)
    return get_preferences(engine, user_id) or {"user_id": user_id}


# ── saved locations ───────────────────────────────────────────────────────────

def _loc_row(row) -> dict:
    return {k: _iso(v) for k, v in dict(row).items()}


def list_locations(engine, user_id: int) -> list[dict]:
    from sqlalchemy import text
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT * FROM saved_locations WHERE user_id = :u "
            "ORDER BY created_at"), {"u": user_id}).mappings().all()
    return [_loc_row(r) for r in rows]


def _normalise_type(t: str | None) -> str:
    t = (t or "custom").lower()
    return t if t in LOCATION_TYPES else "custom"


def create_location(engine, user_id: int, data: dict[str, Any]) -> dict:
    from sqlalchemy import text
    params = {
        "u": user_id,
        "label": data.get("label") or "Saved place",
        "address": data.get("address"),
        "postal_code": data.get("postal_code"),
        "lat": data.get("lat"),
        "lng": data.get("lng"),
        "location_type": _normalise_type(data.get("location_type")),
    }
    with engine.begin() as conn:
        new_id = conn.execute(text(
            "INSERT INTO saved_locations "
            "(user_id, label, address, postal_code, lat, lng, location_type) "
            "VALUES (:u, :label, :address, :postal_code, :lat, :lng, :location_type) "
            "RETURNING id"), params).scalar()
        row = conn.execute(text("SELECT * FROM saved_locations WHERE id = :id"),
                           {"id": new_id}).mappings().first()
    return _loc_row(row)


def update_location(engine, user_id: int, loc_id: int, data: dict[str, Any]) -> dict | None:
    from sqlalchemy import text
    allowed = ("label", "address", "postal_code", "lat", "lng", "location_type")
    fields = {k: data[k] for k in allowed if k in data}
    if "location_type" in fields:
        fields["location_type"] = _normalise_type(fields["location_type"])
    if not fields:
        return _get_location(engine, user_id, loc_id)
    sets = ", ".join(f"{k} = :{k}" for k in fields) + ", updated_at = NOW()"
    params = {**fields, "id": loc_id, "u": user_id}
    with engine.begin() as conn:
        row = conn.execute(text(
            f"UPDATE saved_locations SET {sets} WHERE id = :id AND user_id = :u "
            f"RETURNING *"), params).mappings().first()
    return _loc_row(row) if row else None


def delete_location(engine, user_id: int, loc_id: int) -> bool:
    from sqlalchemy import text
    with engine.begin() as conn:
        res = conn.execute(text(
            "DELETE FROM saved_locations WHERE id = :id AND user_id = :u"),
            {"id": loc_id, "u": user_id})
    return res.rowcount > 0


def _get_location(engine, user_id: int, loc_id: int) -> dict | None:
    from sqlalchemy import text
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT * FROM saved_locations WHERE id = :id AND user_id = :u"),
            {"id": loc_id, "u": user_id}).mappings().first()
    return _loc_row(row) if row else None
