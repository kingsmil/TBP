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
    return _cache.get(key, lambda: _fetch_onemap_theme(spec["onemap"]))
