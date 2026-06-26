"""Amenity points of interest for the map.

Schools come from our own reference data; the rest are proxied from the OneMap
Themes API (services-static reference data) and cached server-side, so they're
fetched once in the background rather than on every client request.

Adding an amenity = one entry in AMENITIES.
"""
from __future__ import annotations

from app.repositories.base import Repository
from app.services.cache import SWRCache
from app.services.commute import onemap_auth

# key -> {label, color, source: "reference"|"onemap", onemap: <queryName>}
AMENITIES: dict[str, dict] = {
    "schools":   {"label": "Schools",          "color": "#2563eb", "source": "reference"},
    "parks":     {"label": "Parks",            "color": "#16a34a", "onemap": "nationalparks"},
    "hawker":    {"label": "Hawker centres",   "color": "#ea580c", "onemap": "ssot_hawkercentres"},
    "hospitals": {"label": "Hospitals",        "color": "#dc2626", "onemap": "moh_hospitals"},
    "sports":    {"label": "Sports facilities", "color": "#9333ea", "onemap": "sportsg_sport_facilities"},
    "community": {"label": "Community clubs",  "color": "#0891b2", "onemap": "communityclubs"},
    "library":   {"label": "Libraries",        "color": "#0d9488", "onemap": "libraries"},
}

_THEME_URL = "https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName={q}"
_cache = SWRCache(ttl=24 * 3600)


def list_amenities() -> list[dict]:
    return [{"key": k, "label": v["label"], "color": v["color"]} for k, v in AMENITIES.items()]


def _fetch_onemap_theme(query: str) -> list[dict]:
    import requests
    token = onemap_auth.current_token()
    if not token:
        return []
    url = _THEME_URL.format(q=query)
    r = requests.get(url, headers={"Authorization": token}, timeout=20)
    if r.status_code == 401:
        token = onemap_auth.refresh()
        if token:
            r = requests.get(url, headers={"Authorization": token}, timeout=20)
    r.raise_for_status()
    out = []
    for row in (r.json() or {}).get("SrchResults", []):
        name, latlng = row.get("NAME"), row.get("LatLng")
        if not name or not latlng:
            continue
        try:
            lat, lon = (float(x) for x in latlng.split(","))
        except (ValueError, AttributeError):
            continue
        out.append({"name": name, "lat": lat, "lon": lon,
                    "address": row.get("ADDRESSSTREETNAME") or row.get("ADDRESS_MYENV") or ""})
    return out


def amenities(repo: Repository, key: str) -> list[dict] | None:
    spec = AMENITIES.get(key)
    if spec is None:
        return None
    if spec.get("source") == "reference":
        return [{"name": s.school_name, "lat": s.point.lat, "lon": s.point.lon,
                 "address": getattr(s, "school_type", "") or ""} for s in repo.schools()]
    # Prefer the seeded DB (no OneMap call); fall back to a live fetch (cached).
    db = _read_db(key)
    if db is not None:
        return db
    return _cache.get(key, lambda: _fetch_onemap_theme(spec["onemap"]))


# ── PostGIS seed: fetched once + refreshed monthly (app.data.amenities) ────────

def _read_db(key: str) -> list[dict] | None:
    """POIs for one OneMap-sourced amenity from the seeded table, or None if the
    table is empty/absent (so callers fall back to a live fetch)."""
    try:
        from app.api.deps import get_engine_or_none
        from sqlalchemy import text
        engine = get_engine_or_none()
        if engine is None:
            return None
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT name, lat, lon, address FROM amenity_pois WHERE amenity = :k "
                "ORDER BY name"), {"k": key}).mappings().all()
        return [dict(r) for r in rows] if rows else None
    except Exception:
        return None


def onemap_keys() -> list[str]:
    return [k for k, v in AMENITIES.items() if v.get("onemap")]


def fetch_for_seed(key: str) -> list[dict]:
    """Live OneMap fetch for one amenity key (used by the seed/refresh job)."""
    spec = AMENITIES.get(key) or {}
    if not spec.get("onemap"):
        return []
    return _fetch_onemap_theme(spec["onemap"])


def persist(engine, key: str, rows: list[dict]) -> int:
    from sqlalchemy import text
    if not rows:
        return 0
    payload = [{"amenity": key, "name": r["name"], "lat": r["lat"],
                "lon": r["lon"], "address": r.get("address")} for r in rows]
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM amenity_pois WHERE amenity = :k"), {"k": key})
        conn.execute(text(
            "INSERT INTO amenity_pois (amenity, name, lat, lon, address, fetched_at) "
            "VALUES (:amenity, :name, :lat, :lon, :address, NOW())"), payload)
    return len(payload)


def db_age_days(engine):
    from datetime import datetime, timezone
    from sqlalchemy import text
    with engine.connect() as conn:
        ts = conn.execute(text("SELECT MAX(fetched_at) FROM amenity_pois")).scalar()
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0
