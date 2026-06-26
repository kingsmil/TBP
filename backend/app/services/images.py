"""Property images for the detail view, with a layered fallback:

  1. Real HDB listing photo (HDB Flat Portal) when the block has an active listing
  2. Google Street View Static — a real façade — when GOOGLE_MAPS_API_KEY is set
  3. Mapillary — free crowd-sourced street photo — when MAPILLARY_TOKEN is set
  4. OneMap Static Map — a free location thumbnail, available for any lat/lon

All tokens/keys stay server-side; the frontend just points an <img> at
/image/property. Bytes are cached in-process so we don't re-fetch the same
location repeatedly.
"""
from __future__ import annotations

import functools
import logging
import os

from app.services.commute import onemap_auth

log = logging.getLogger(__name__)

LISTING_BASE = "https://static.homes.hdb.gov.sg/"
_ONEMAP_STATIC = "https://www.onemap.gov.sg/api/staticmap/getStaticImage"
_STREETVIEW = "https://maps.googleapis.com/maps/api/streetview"
_MAPILLARY = "https://graph.mapillary.com/images"


def listing_photo_url(repo, block_id: int) -> str | None:
    """Public URL of a real listing photo for the block, if one exists."""
    try:
        for a in repo.active_listings_for_block(block_id):
            if getattr(a, "photo_path", None):
                return LISTING_BASE + a.photo_path
    except Exception:
        return None
    return None


@functools.lru_cache(maxsize=1024)
def _streetview(lat: float, lon: float) -> bytes | None:
    import requests
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        return None
    try:
        r = requests.get(_STREETVIEW, params={
            "size": "640x360", "location": f"{lat},{lon}", "fov": 80,
            "return_error_code": "true", "key": key,
        }, timeout=15)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            return r.content
    except Exception as exc:
        log.warning("Street View fetch failed: %s", exc)
    return None


@functools.lru_cache(maxsize=2048)
def _mapillary(lat: float, lon: float) -> bytes | None:
    """Nearest crowd-sourced street photo within ~100 m, or None."""
    import requests
    token = os.environ.get("MAPILLARY_TOKEN")
    if not token:
        return None
    d = 0.0009  # ~100 m bbox
    try:
        r = requests.get(_MAPILLARY, params={
            "fields": "id,thumb_1024_url",
            "bbox": f"{lon - d},{lat - d},{lon + d},{lat + d}",
            "limit": 1,
        }, headers={"Authorization": f"OAuth {token}"}, timeout=15)
        if r.status_code != 200:
            return None
        data = (r.json() or {}).get("data") or []
        url = data[0].get("thumb_1024_url") if data else None
        if not url:
            return None
        img = requests.get(url, timeout=15)  # pre-signed CDN URL, no token needed
        if img.status_code == 200 and img.headers.get("content-type", "").startswith("image"):
            return img.content
    except Exception as exc:
        log.warning("Mapillary fetch failed: %s", exc)
    return None


@functools.lru_cache(maxsize=2048)
def _onemap_static(lat: float, lon: float) -> bytes | None:
    import requests
    token = onemap_auth.current_token()
    if not token:
        return None
    try:
        r = requests.get(_ONEMAP_STATIC, params={
            "layerchosen": "default", "latitude": lat, "longitude": lon,
            "zoom": 17, "width": 480, "height": 300,  # OneMap caps at 512x512
            "points": f'[{lat},{lon},"234,67,53"]',
        }, headers={"Authorization": token}, timeout=15)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception as exc:
        log.warning("OneMap static map fetch failed: %s", exc)
    return None


def location_image(lat: float, lon: float) -> tuple[bytes, str] | None:
    """Street View → Mapillary → OneMap static map. Returns (bytes, mime)."""
    lat, lon = round(lat, 5), round(lon, 5)
    sv = _streetview(lat, lon)
    if sv is not None:
        return sv, "image/jpeg"
    ml = _mapillary(lat, lon)
    if ml is not None:
        return ml, "image/jpeg"
    om = _onemap_static(lat, lon)
    if om is not None:
        return om, "image/png"
    return None
