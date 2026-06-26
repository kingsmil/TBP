"""URA Private Residential Property Transactions client + mock fallback.

Live mode: mints a daily token from URA_ACCESS_KEY, then pulls the 4 rolling
batches (~60 months) of the PMI_Resi_Transaction service. Mock mode (no access
key, or PRIVATE_PROPERTY_MOCK_MODE=true): returns bundled fixtures.

Results are normalised + cached server-side (SWR), so we hit URA rarely rather
than on every client request — same pattern as the BTO / amenity layers.
"""
from __future__ import annotations

import logging
import threading
import time

from app.config import settings
from app.services.cache import SWRCache
from app.services.private_property import normalise
from app.services.private_property.fixtures import ura_result_fixture

log = logging.getLogger(__name__)

_cache = SWRCache(ttl=24 * 3600)  # URA data updates ~weekly; refresh daily.
_CACHE_KEY = "ura_transactions"
_BATCHES = (1, 2, 3, 4)

# URA tokens expire daily. We mint one, cache it, and auto-renew when it's past
# this TTL (kept under 24h for safety) or when the API rejects it mid-flight.
_TOKEN_TTL_S = 23 * 3600
_token: dict = {"value": None, "expires": 0.0}
_token_lock = threading.Lock()


def is_mock() -> bool:
    return settings.private_property_mock_mode


def _mint_token() -> str | None:
    import requests
    try:
        r = requests.get(settings.ura_token_url,
                         headers={"AccessKey": settings.ura_access_key or "",
                                  "User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
        if str(data.get("Status", "")).lower() == "success" and data.get("Result"):
            return data["Result"]
        log.warning("URA token mint returned no token: %s", data.get("Message"))
        return None
    except Exception as exc:
        log.warning("URA token mint failed: %s", exc)
        return None


def current_token(force: bool = False) -> str | None:
    """Return a valid token, auto-renewing when expired (or forced).

    Tokens are minted from the permanent access key and live ~1 day; we cache
    one and renew it past _TOKEN_TTL_S or on demand (e.g. after a 401)."""
    with _token_lock:
        if not force and _token["value"] and time.time() < _token["expires"]:
            return _token["value"]
        tok = _mint_token()
        if tok:
            _token["value"] = tok
            _token["expires"] = time.time() + _TOKEN_TTL_S
            log.info("URA token renewed (valid ~%dh).", _TOKEN_TTL_S // 3600)
        return tok


def _fetch_live() -> list[dict]:
    """Fetch + normalise all batches. Returns [] on failure (caller falls back)."""
    import requests
    token = current_token()
    if not token:
        return []
    rows: list[dict] = []
    for batch in _BATCHES:
        for attempt in (1, 2):  # one retry with a freshly-renewed token
            headers = {"AccessKey": settings.ura_access_key or "", "Token": token,
                       "User-Agent": "Mozilla/5.0"}
            try:
                r = requests.get(settings.ura_api_url,
                                 params={"service": "PMI_Resi_Transaction", "batch": batch},
                                 headers=headers, timeout=60)
                if r.status_code == 401 and attempt == 1:
                    token = current_token(force=True) or token  # token expired → renew + retry
                    continue
                r.raise_for_status()
                payload = r.json() or {}
                if str(payload.get("Status", "")).lower() not in ("success", ""):
                    # An expired-token message can also arrive as a 200 body.
                    if "token" in str(payload.get("Message", "")).lower() and attempt == 1:
                        token = current_token(force=True) or token
                        continue
                    log.warning("URA batch %s status: %s", batch, payload.get("Message"))
                rows.extend(normalise.normalise_batch(payload.get("Result") or []))
                break
            except Exception as exc:
                log.warning("URA batch %s fetch failed (attempt %d): %s", batch, attempt, exc)
                break
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
