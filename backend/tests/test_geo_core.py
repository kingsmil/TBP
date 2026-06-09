"""Tests for the dependency-free geospatial core (CRS + geometry ops)."""
import math
import unittest

from app.core.crs import wgs84_to_svy21
from app.core.geo import (
    Point,
    count_within_m,
    distance_m,
    k_nearest,
    nearest,
    point_in_polygon,
    point_in_ring,
)

# SVY21 false origin (EPSG:3414).
FALSE_E, FALSE_N = 28001.642, 38744.572
ORIGIN_LON, ORIGIN_LAT = 103.833333, 1.366666


def haversine_m(a: Point, b: Point) -> float:
    """Independent great-circle distance, used only to validate the core."""
    r = 6371000.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlmb = math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class TestCrs(unittest.TestCase):
    def test_origin_maps_to_false_easting_northing(self):
        e, n = wgs84_to_svy21(ORIGIN_LON, ORIGIN_LAT)
        self.assertAlmostEqual(e, FALSE_E, places=2)
        self.assertAlmostEqual(n, FALSE_N, places=2)

    def test_point_north_increases_northing(self):
        e0, n0 = wgs84_to_svy21(ORIGIN_LON, ORIGIN_LAT)
        e1, n1 = wgs84_to_svy21(ORIGIN_LON, ORIGIN_LAT + 0.01)
        self.assertGreater(n1, n0)
        self.assertAlmostEqual(e1, e0, places=1)  # due north -> easting ~unchanged


class TestDistance(unittest.TestCase):
    def test_zero_distance(self):
        p = Point(103.85, 1.30)
        self.assertAlmostEqual(distance_m(p, p), 0.0, places=6)

    def test_symmetry(self):
        a, b = Point(103.85, 1.30), Point(103.90, 1.35)
        self.assertAlmostEqual(distance_m(a, b), distance_m(b, a), places=6)

    def test_matches_haversine_within_tolerance(self):
        # Raffles Place -> Tampines (~12 km). SVY21 planar should match
        # great-circle to well within 1%.
        raffles = Point(103.8519, 1.2841)
        tampines = Point(103.9568, 1.3496)
        d_svy = distance_m(raffles, tampines)
        d_hav = haversine_m(raffles, tampines)
        self.assertLess(abs(d_svy - d_hav) / d_hav, 0.01)
        self.assertGreater(d_svy, 10000)  # sanity: it's a long hop


class TestNearestAndCounts(unittest.TestCase):
    def setUp(self):
        self.origin = Point(103.8500, 1.3000)
        self.stations = [
            ("A", Point(103.8510, 1.3000)),   # ~111 m east
            ("B", Point(103.8700, 1.3000)),   # ~2.2 km east
            ("C", Point(103.8500, 1.3050)),   # ~553 m north
        ]

    def test_nearest(self):
        key, _, dist = nearest(self.origin, self.stations)
        self.assertEqual(key, "A")
        self.assertLess(dist, 200)

    def test_nearest_empty(self):
        self.assertIsNone(nearest(self.origin, []))

    def test_k_nearest_sorted(self):
        result = k_nearest(self.origin, self.stations, k=2)
        self.assertEqual([r[0] for r in result], ["A", "C"])
        self.assertLessEqual(result[0][2], result[1][2])

    def test_count_within_radius(self):
        # Within 600 m we expect A (~111 m) and C (~553 m), not B (~2.2 km).
        self.assertEqual(count_within_m(self.origin, self.stations, 600), 2)
        self.assertEqual(count_within_m(self.origin, self.stations, 50), 0)


class TestPointInPolygon(unittest.TestCase):
    def setUp(self):
        # A ~0.02 deg square around (103.85, 1.30).
        self.ring = [
            (103.84, 1.29), (103.86, 1.29), (103.86, 1.31), (103.84, 1.31),
        ]

    def test_inside(self):
        self.assertTrue(point_in_ring(Point(103.85, 1.30), self.ring))

    def test_outside(self):
        self.assertFalse(point_in_ring(Point(103.90, 1.30), self.ring))

    def test_polygon_with_hole(self):
        hole = [(103.848, 1.298), (103.852, 1.298),
                (103.852, 1.302), (103.848, 1.302)]
        poly = [self.ring, hole]
        # Point inside the hole is NOT in the polygon.
        self.assertFalse(point_in_polygon(Point(103.850, 1.300), poly))
        # Point inside outer ring but outside hole IS in the polygon.
        self.assertTrue(point_in_polygon(Point(103.858, 1.308), poly))


if __name__ == "__main__":
    unittest.main()
