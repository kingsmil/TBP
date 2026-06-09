"""Dependency-free geospatial operations on Singapore coordinates.

These mirror the PostGIS functions the production path uses, with identical
metric semantics (all distances in SVY21 metres):

  distance_m        ~ ST_Distance(a.geom_svy21, b.geom_svy21)
  within_m          ~ ST_DWithin(a.geom_svy21, b.geom_svy21, r)
  nearest           ~ ORDER BY geom_svy21 <-> geom_svy21 LIMIT 1  (KNN)
  k_nearest         ~ ... LIMIT k
  point_in_ring     ~ ST_Contains(polygon, point)  (ray casting)
  count_within_m    ~ count(*) ... WHERE ST_DWithin(...)

Coordinates are (lon, lat) in WGS84 degrees, matching GeoJSON axis order.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from app.core.crs import wgs84_to_svy21

LonLat = tuple[float, float]


@dataclass(frozen=True)
class Point:
    lon: float
    lat: float

    def svy21(self) -> tuple[float, float]:
        return wgs84_to_svy21(self.lon, self.lat)


def distance_m(a: Point, b: Point) -> float:
    """Planar distance in metres via SVY21 projection."""
    ax, ay = a.svy21()
    bx, by = b.svy21()
    return math.hypot(ax - bx, ay - by)


def within_m(a: Point, b: Point, radius_m: float) -> bool:
    return distance_m(a, b) <= radius_m


def nearest(origin: Point, candidates: Iterable[tuple[object, Point]]):
    """Return (key, point, distance_m) for the closest candidate, or None."""
    best = None
    for key, pt in candidates:
        d = distance_m(origin, pt)
        if best is None or d < best[2]:
            best = (key, pt, d)
    return best


def k_nearest(origin: Point, candidates: Iterable[tuple[object, Point]], k: int):
    """Return up to k (key, point, distance_m) tuples sorted by distance."""
    scored = [(key, pt, distance_m(origin, pt)) for key, pt in candidates]
    scored.sort(key=lambda x: x[2])
    return scored[:k]


def count_within_m(origin: Point, candidates: Iterable[tuple[object, Point]],
                   radius_m: float) -> int:
    return sum(1 for _, pt in candidates if distance_m(origin, pt) <= radius_m)


def point_in_ring(point: Point, ring: Sequence[LonLat]) -> bool:
    """Ray-casting point-in-polygon test for a single ring (lon, lat).

    Works in projected metres so it is consistent with the rest of the core.
    The ring may be open or closed.
    """
    px, py = point.svy21()
    pts = [wgs84_to_svy21(lon, lat) for lon, lat in ring]
    n = len(pts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        intersects = ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def point_in_polygon(point: Point, polygon: Sequence[Sequence[LonLat]]) -> bool:
    """Point in a polygon defined as [outer_ring, hole1, hole2, ...]."""
    if not polygon:
        return False
    if not point_in_ring(point, polygon[0]):
        return False
    return not any(point_in_ring(point, hole) for hole in polygon[1:])
