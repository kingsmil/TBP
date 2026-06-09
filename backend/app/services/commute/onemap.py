"""OneMap public-transport routing provider (production path).

Calls the OneMap routing API for real door-to-door public-transport times.
Requires a OneMap API token (ONEMAP_TOKEN). Not exercised by the test suite —
the sandbox has no network/token — but it implements the same CommuteProvider
interface, so the optimizer/couple/lifestyle services use it unchanged once a
token is configured.

Docs: https://www.onemap.gov.sg/apidocs/ (routingsvc).
Results are cached (coordinates rounded to ~10 m) to respect rate limits; in
production point `cache` at Redis instead of the in-process dict.
"""
from __future__ import annotations

import datetime as _dt
import os

from app.core.geo import Point
from app.services.commute.models import CommuteResult
from app.services.commute.provider import CommuteProvider

ROUTE_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"


class OneMapCommuteProvider(CommuteProvider):
    def __init__(self, token: str | None = None, *, max_walk_m: int = 1000,
                 timeout: float = 10.0, cache: dict | None = None):
        self._token = token or os.environ.get("ONEMAP_TOKEN")
        if not self._token:
            raise RuntimeError("ONEMAP_TOKEN not set")
        self._max_walk_m = max_walk_m
        self._timeout = timeout
        self._cache = cache if cache is not None else {}

    @staticmethod
    def _key(origin: Point, dest: Point, mode: str) -> str:
        return (f"{round(origin.lat, 5)},{round(origin.lon, 5)}|"
                f"{round(dest.lat, 5)},{round(dest.lon, 5)}|{mode}")

    def route(self, origin: Point, dest: Point, mode: str = "pt") -> CommuteResult:
        cache_key = self._key(origin, dest, mode)
        if cache_key in self._cache:
            return self._cache[cache_key]

        import requests  # imported lazily so the module loads without the dep

        now = _dt.datetime.now()
        params = {
            "start": f"{origin.lat},{origin.lon}",
            "end": f"{dest.lat},{dest.lon}",
            "routeType": "pt" if mode == "pt" else mode,
            "date": now.strftime("%m-%d-%Y"),
            "time": now.strftime("%H:%M:%S"),
            "mode": "TRANSIT",
            "maxWalkDistance": self._max_walk_m,
            "numItineraries": 1,
        }
        resp = requests.get(
            ROUTE_URL, params=params,
            headers={"Authorization": self._token}, timeout=self._timeout,
        )
        resp.raise_for_status()
        result = self._parse(resp.json(), origin, dest, mode)
        self._cache[cache_key] = result
        return result

    @staticmethod
    def _parse(payload: dict, origin: Point, dest: Point, mode: str) -> CommuteResult:
        plan = payload.get("plan") or {}
        itineraries = plan.get("itineraries") or []
        if not itineraries:
            raise ValueError("OneMap returned no itineraries")
        it = itineraries[0]
        total_min = float(it.get("duration", 0)) / 60.0
        walk_min = float(it.get("walkTime", 0)) / 60.0
        transfers = int(it.get("transfers", 0))
        walk_dist = float(it.get("walkDistance", 0.0))
        return CommuteResult(round(total_min, 2), round(walk_min, 2),
                             transfers, round(walk_dist, 2), mode)
