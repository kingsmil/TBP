"""Tests for the appreciation-ranking auto-refresh scheduler."""
from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from app.analysis import scheduler


class _FakeConn:
    def __init__(self, scalar_val):
        self._v = scalar_val

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        m = mock.Mock()
        m.scalar.return_value = self._v
        return m


class _FakeEngine:
    def __init__(self, scalar_val):
        self._v = scalar_val

    def connect(self):
        return _FakeConn(self._v)


class TestSchedulerConfig(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in
                       ("RANKINGS_AUTO_REFRESH", "RANKINGS_STALE_DAYS")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_enabled_by_default(self):
        self.assertTrue(scheduler._enabled())

    def test_disable_flag(self):
        for val in ("false", "0", "no", "FALSE"):
            os.environ["RANKINGS_AUTO_REFRESH"] = val
            self.assertFalse(scheduler._enabled())

    def test_stale_days_default_and_override(self):
        self.assertEqual(scheduler._stale_days(), 30)
        os.environ["RANKINGS_STALE_DAYS"] = "7"
        self.assertEqual(scheduler._stale_days(), 7)

    def test_stale_days_bad_value_falls_back(self):
        os.environ["RANKINGS_STALE_DAYS"] = "abc"
        self.assertEqual(scheduler._stale_days(), 30)


class TestAge(unittest.TestCase):
    def test_age_none_when_empty(self):
        self.assertIsNone(scheduler._age_days(_FakeEngine(None)))

    def test_age_computed_from_timestamp(self):
        ts = datetime.now(timezone.utc) - timedelta(days=40)
        age = scheduler._age_days(_FakeEngine(ts))
        self.assertAlmostEqual(age, 40, delta=1)

    def test_age_handles_naive_timestamp(self):
        ts = datetime.utcnow() - timedelta(days=10)  # naive
        age = scheduler._age_days(_FakeEngine(ts))
        self.assertAlmostEqual(age, 10, delta=1)


class TestStart(unittest.TestCase):
    def test_returns_none_when_disabled(self):
        with mock.patch.dict(os.environ, {"RANKINGS_AUTO_REFRESH": "false"}):
            self.assertIsNone(scheduler.start_ranking_refresh())

    def test_returns_none_when_no_database(self):
        with mock.patch.dict(os.environ, {"RANKINGS_AUTO_REFRESH": "true"}), \
             mock.patch("app.api.deps.get_engine_or_none", return_value=None):
            self.assertIsNone(scheduler.start_ranking_refresh())


if __name__ == "__main__":
    unittest.main()
