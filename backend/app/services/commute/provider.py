"""Commute providers (Phase 3).

A CommuteProvider estimates a single origin->destination journey. Two
implementations exist:

  * HeuristicCommuteProvider — dependency-free, deterministic. Used for tests
    and as the offline fallback when no OneMap token is configured. Models a
    walk -> rail -> walk public-transport journey using the MRT network.
  * OneMapCommuteProvider (app.services.commute.onemap) — calls the real OneMap
    public-transport routing API. Production path; not exercised in tests.

All downstream Phase 3 logic depends only on this interface, so swapping the
heuristic for OneMap is a configuration change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.geo import Point, distance_m, nearest
from app.core.models import MrtStation
from app.services.commute.models import CommuteResult

# Heuristic constants (rough Singapore averages).
WALK_SPEED_M_PER_MIN = 80.0     # ~4.8 km/h
RAIL_SPEED_M_PER_MIN = 600.0    # ~36 km/h effective incl. dwell time
DRIVE_SPEED_M_PER_MIN = 500.0   # ~30 km/h urban average
TRANSFER_PENALTY_MIN = 5.0
BOARDING_WAIT_MIN = 4.0
WALK_ONLY_THRESHOLD_M = 800.0   # below this, just walk


class CommuteProvider(ABC):
    @abstractmethod
    def route(self, origin: Point, dest: Point, mode: str = "pt") -> CommuteResult:
        ...


class HeuristicCommuteProvider(CommuteProvider):
    def __init__(self, mrt_stations: list[MrtStation]):
        # Only operational stations are usable for current commute estimates.
        self._mrt = [(m.station_id, m.point, m.line_name)
                     for m in mrt_stations if m.status == "operational"]

    def _nearest_mrt(self, p: Point):
        if not self._mrt:
            return None
        key, pt, _ = nearest(p, [(i, pt) for i, pt, _ in self._mrt])
        line = next(ln for i, _, ln in self._mrt if i == key)
        return key, pt, line

    def route(self, origin: Point, dest: Point, mode: str = "pt") -> CommuteResult:
        direct = distance_m(origin, dest)

        if mode == "walk" or direct <= WALK_ONLY_THRESHOLD_M:
            minutes = direct / WALK_SPEED_M_PER_MIN
            return CommuteResult(round(minutes, 2), round(minutes, 2), 0,
                                 round(direct, 2), "walk")

        if mode == "drive":
            minutes = direct / DRIVE_SPEED_M_PER_MIN
            return CommuteResult(round(minutes, 2), 0.0, 0, round(direct, 2), "drive")

        # Public transport: walk -> rail -> walk.
        o = self._nearest_mrt(origin)
        d = self._nearest_mrt(dest)
        if o is None or d is None:
            minutes = direct / WALK_SPEED_M_PER_MIN
            return CommuteResult(round(minutes, 2), round(minutes, 2), 0,
                                 round(direct, 2), "walk")

        _, o_pt, o_line = o
        d_id, d_pt, d_line = d
        walk_o = distance_m(origin, o_pt) / WALK_SPEED_M_PER_MIN
        walk_d = distance_m(dest, d_pt) / WALK_SPEED_M_PER_MIN
        rail = distance_m(o_pt, d_pt) / RAIL_SPEED_M_PER_MIN
        same_station = (o[0] == d_id)
        transfers = 0 if same_station or o_line == d_line else 1
        total = (BOARDING_WAIT_MIN + walk_o + rail
                 + transfers * TRANSFER_PENALTY_MIN + walk_d)
        return CommuteResult(round(total, 2), round(walk_o + walk_d, 2),
                             transfers, round(direct, 2), "pt")
