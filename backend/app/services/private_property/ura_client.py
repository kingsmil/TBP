"""URA Private Residential Property Transactions client + mock fallback.

Live mode: mints a daily token from URA_ACCESS_KEY, then pulls the 4 rolling
batches (~60 months) of the PMI_Resi_Transaction service. Mock mode (no access
key, or PRIVATE_PROPERTY_MOCK_MODE=true): returns bundled fixtures.

Results are normalised + cached server-side (SWR), so we hit URA rarely rather
than on every client request — same pattern as the BTO / amenity layers.
"""
from __future__ import annotations

import logging

from app.config import settings
from app.services.cache import SWRCache
from app.services.private_property import normalise
from app.services.private_property.fixtures import ura_result_fixture

log = logging.getLogger(__name__)

_cache = SWRCache(ttl=24 * 3600)  # URA data updates ~weekly; refresh daily.
_CACHE_KEY = "ura_transactions"
_BATCHES = (1, 2, 3, 4)


def is_mock() -> bool:
    return settings.private_property_mock_mode


def _fetch_token() -> str | None:
    import requests
    try:
        r = requests.get(settings.ura_token_url,
                         headers={"AccessKey": settings.ura_access_key or "",
                                  "User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        return data.get("Result") or None
    except Exception as exc:
        log.warning("URA token fetch failed: %s", exc)
        return None


def _fetch_live() -> list[dict]:
    """Fetch + normalise all batches. Returns [] on failure (caller falls back)."""
    import requests
    token = _fetch_token()
    if not token:
        return []
    rows: list[dict] = []
    headers = {"AccessKey": settings.ura_access_key or "", "Token": token,
               "User-Agent": "Mozilla/5.0"}
    for batch in _BATCHES:
        try:
            r = requests.get(settings.ura_api_url,
                             params={"service": "PMI_Resi_Transaction", "batch": batch},
                             headers=headers, timeout=40)
            r.raise_for_status()
            payload = r.json() or {}
            if str(payload.get("Status", "")).lower() not in ("success", ""):
                log.warning("URA batch %s status: %s", batch, payload.get("Message"))
            rows.extend(normalise.normalise_batch(payload.get("Result") or []))
        except Exception as exc:
            log.warning("URA batch %s fetch failed: %s", batch, exc)
    return rows


def _load() -> list[dict]:
    if is_mock():
        return normalise.normalise_batch(ura_result_fixture())
    rows = _fetch_live()
    if not rows:
        log.warning("URA returned no rows — falling back to fixtures.")
        return normalise.normalise_batch(ura_result_fixture())
    return rows


def all_transactions() -> list[dict]:
    """All normalised transactions (cached). Mock fixtures when no creds."""
    return _cache.get(_CACHE_KEY, _load)


def refresh() -> list[dict]:
    """Force a re-fetch (used by the background scheduler)."""
    _cache.invalidate(_CACHE_KEY)
    return all_transactions()
