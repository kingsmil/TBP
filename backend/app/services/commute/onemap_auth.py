"""OneMap token manager — mints and refreshes the API token automatically.

OneMap access tokens have a ~3-day TTL. Instead of pasting a fresh token in by
hand every few days, set ONEMAP_EMAIL + ONEMAP_PASSWORD and this manager mints a
token on demand, caches it, re-mints it shortly before expiry, and re-mints on a
401 (see OneMapCommuteProvider). A static ONEMAP_TOKEN is still honoured as-is
(no refresh) for environments that only have a token and no credentials.

Thread-safe: the optimizer/heatmap run blocks through a threadpool.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time

log = logging.getLogger(__name__)

TOKEN_URL = "https://www.onemap.gov.sg/api/auth/post/getToken"
# Re-mint this many seconds before the token's own expiry, so callers never see
# an expired token at the boundary.
_REFRESH_SKEW_S = 6 * 3600

_lock = threading.Lock()
_token: str | None = None
_exp: float = 0.0


def _has_credentials() -> bool:
    return bool(os.environ.get("ONEMAP_EMAIL") and os.environ.get("ONEMAP_PASSWORD"))


def _decode_exp(token: str) -> float:
    """Unix expiry from a OneMap JWT, or 0 if it can't be read."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload)).get("exp", 0))
    except Exception:
        return 0.0


def _mint() -> str:
    """Mint a fresh token from ONEMAP_EMAIL/ONEMAP_PASSWORD."""
    email = os.environ.get("ONEMAP_EMAIL")
    password = os.environ.get("ONEMAP_PASSWORD")
    if not (email and password):
        raise RuntimeError("ONEMAP_EMAIL/ONEMAP_PASSWORD not set; cannot mint token")
    import requests
    resp = requests.post(TOKEN_URL, json={"email": email, "password": password},
                         timeout=15)
    resp.raise_for_status()
    token = (resp.json() or {}).get("access_token")
    if not token:
        raise RuntimeError("OneMap getToken returned no access_token")
    log.info("Minted a fresh OneMap token (expires in ~3 days).")
    return token


def _store(token: str) -> str:
    global _token, _exp
    _token = token
    _exp = _decode_exp(token)
    return token


def current_token() -> str | None:
    """A usable token, minting/refreshing as needed. None if neither credentials
    nor a static ONEMAP_TOKEN are configured."""
    with _lock:
        if _token and time.time() < _exp - _REFRESH_SKEW_S:
            return _token
        if _has_credentials():
            return _store(_mint())
        static = os.environ.get("ONEMAP_TOKEN")
        if static:
            return _store(static)
        return None


def refresh() -> str | None:
    """Force a re-mint (e.g. after a 401). Returns the new token, or the existing
    one when there are no credentials to mint with."""
    with _lock:
        if _has_credentials():
            return _store(_mint())
        return _token or os.environ.get("ONEMAP_TOKEN")


def available() -> bool:
    """True if a token can be obtained (static token or mintable credentials)."""
    return _has_credentials() or bool(os.environ.get("ONEMAP_TOKEN"))


def _reset_for_tests() -> None:
    global _token, _exp
    with _lock:
        _token, _exp = None, 0.0
