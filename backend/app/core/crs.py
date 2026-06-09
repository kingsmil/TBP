"""Coordinate transforms used by the dependency-free geospatial core.

We implement the official SVY21 (EPSG:3414) projection so that distances
computed in Python match what PostGIS would produce via
`ST_Transform(geom, 3414)` followed by `ST_Distance(...)`, to sub-metre
accuracy. SVY21 is a Transverse Mercator projection on the WGS84 ellipsoid
with the parameters below (published by the Singapore Land Authority).

Keeping this here means the in-memory repository and the PostGIS repository
share the same metric semantics: distance/area work in projected metres, and
no query ever measures distance in raw degrees.
"""
from __future__ import annotations

import math

# SVY21 / EPSG:3414 projection parameters (Transverse Mercator, WGS84 ellipsoid).
_A = 6378137.0                  # semi-major axis (m)
_F = 1.0 / 298.257223563        # flattening
_ORIGIN_LAT = math.radians(1.366666)     # latitude of origin
_ORIGIN_LON = math.radians(103.833333)   # central meridian
_K0 = 1.0                       # scale factor
_FALSE_N = 38744.572            # false northing (m)
_FALSE_E = 28001.642            # false easting (m)

_E2 = _F * (2 - _F)             # eccentricity squared
_N = _F / (2 - _F)


def _meridian_arc(lat: float) -> float:
    """Meridian distance from the equator to `lat` (radians)."""
    n, n2, n3, n4 = _N, _N**2, _N**3, _N**4
    g = _A / (1 + n) * (1 + n2 / 4 + n4 / 64)
    term = (
        lat
        - (3 * n / 2 - 9 * n3 / 16) * math.sin(2 * lat)
        + (15 * n2 / 16 - 15 * n4 / 32) * math.sin(4 * lat)
        - (35 * n3 / 48) * math.sin(6 * lat)
        + (315 * n4 / 512) * math.sin(8 * lat)
    )
    return g * term


def wgs84_to_svy21(lon_deg: float, lat_deg: float) -> tuple[float, float]:
    """Project (lon, lat) in WGS84 degrees to SVY21 (easting, northing) metres."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    t = math.tan(lat)

    rho = _A * (1 - _E2) / (1 - _E2 * sin_lat**2) ** 1.5
    nu = _A / math.sqrt(1 - _E2 * sin_lat**2)
    psi = nu / rho
    w = lon - _ORIGIN_LON

    M = _meridian_arc(lat)
    M0 = _meridian_arc(_ORIGIN_LAT)

    # Easting series.
    e_t1 = nu * cos_lat
    e_t2 = nu * cos_lat**3 / 6 * (psi - t**2)
    e_t3 = nu * cos_lat**5 / 120 * (
        4 * psi**3 * (1 - 6 * t**2) + psi**2 * (1 + 8 * t**2)
        - psi * 2 * t**2 + t**4
    )
    e_t4 = nu * cos_lat**7 / 5040 * (61 - 479 * t**2 + 179 * t**4 - t**6)
    easting = _FALSE_E + _K0 * (w * e_t1 + w**3 * e_t2 + w**5 * e_t3 + w**7 * e_t4)

    # Northing series.
    n_t1 = M - M0
    n_t2 = w**2 / 2 * nu * sin_lat * cos_lat
    n_t3 = w**4 / 24 * nu * sin_lat * cos_lat**3 * (4 * psi**2 + psi - t**2)
    n_t4 = w**6 / 720 * nu * sin_lat * cos_lat**5 * (
        8 * psi**4 * (11 - 24 * t**2) - 28 * psi**3 * (1 - 6 * t**2)
        + psi**2 * (1 - 32 * t**2) - psi * 2 * t**2 + t**4
    )
    n_t5 = w**8 / 40320 * nu * sin_lat * cos_lat**7 * (
        1385 - 3111 * t**2 + 543 * t**4 - t**6
    )
    northing = _FALSE_N + _K0 * (n_t1 + n_t2 + n_t3 + n_t4 + n_t5)

    return easting, northing
