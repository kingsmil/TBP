"""Tests for the stale-while-revalidate cache."""
from __future__ import annotations

import time
import unittest

from app.services.cache import SWRCache


class TestSWRCache(unittest.TestCase):
    def test_computes_once_then_serves_cached(self):
        calls = {"n": 0}

        def compute():
            calls["n"] += 1
            return calls["n"]

        c = SWRCache(ttl=100)
        self.assertEqual(c.get("k", compute), 1)
        self.assertEqual(c.get("k", compute), 1)   # cached — no recompute
        self.assertEqual(calls["n"], 1)

    def test_stale_serves_old_value_then_refreshes_in_background(self):
        calls = {"n": 0}

        def compute():
            calls["n"] += 1
            return calls["n"]

        c = SWRCache(ttl=0)                         # everything is immediately stale
        self.assertEqual(c.get("k", compute), 1)   # first compute (inline)
        self.assertEqual(c.get("k", compute), 1)   # served STALE while refresh runs
        time.sleep(0.3)                            # let the background refresh finish
        self.assertGreaterEqual(calls["n"], 2)
        self.assertGreaterEqual(c.get("k", compute), 2)

    def test_warm_prefills_in_background(self):
        calls = {"n": 0}

        def compute():
            calls["n"] += 1
            return "value"

        c = SWRCache(ttl=100)
        c.warm("k", compute)
        time.sleep(0.3)
        self.assertEqual(c.get("k", compute), "value")
        self.assertEqual(calls["n"], 1)            # warm computed it; get served cache

    def test_invalidate_forces_recompute(self):
        calls = {"n": 0}

        def compute():
            calls["n"] += 1
            return calls["n"]

        c = SWRCache(ttl=100)
        self.assertEqual(c.get("k", compute), 1)
        c.invalidate("k")
        self.assertEqual(c.get("k", compute), 2)   # recomputed after invalidation


if __name__ == "__main__":
    unittest.main()
