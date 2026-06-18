"""Tests for the OneMap token auto-refresh manager."""
from __future__ import annotations

import base64
import json
import os
import time
import unittest
from unittest import mock

from app.services.commute import onemap_auth


def _fake_jwt(exp: float) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"hdr.{payload}.sig"


def _resp(token: str):
    r = mock.Mock()
    r.json.return_value = {"access_token": token}
    r.raise_for_status.return_value = None
    return r


class TestOneMapAuth(unittest.TestCase):
    def setUp(self):
        onemap_auth._reset_for_tests()
        self._saved = {k: os.environ.get(k) for k in
                       ("ONEMAP_EMAIL", "ONEMAP_PASSWORD", "ONEMAP_TOKEN")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        onemap_auth._reset_for_tests()

    def test_no_config_returns_none(self):
        self.assertIsNone(onemap_auth.current_token())
        self.assertFalse(onemap_auth.available())

    def test_static_token_used_without_credentials(self):
        os.environ["ONEMAP_TOKEN"] = _fake_jwt(time.time() + 3 * 86400)
        self.assertTrue(onemap_auth.available())
        self.assertEqual(onemap_auth.current_token(), os.environ["ONEMAP_TOKEN"])

    def test_mints_from_credentials(self):
        os.environ["ONEMAP_EMAIL"] = "a@b.com"
        os.environ["ONEMAP_PASSWORD"] = "pw"
        token = _fake_jwt(time.time() + 3 * 86400)
        with mock.patch("requests.post", return_value=_resp(token)) as post:
            self.assertEqual(onemap_auth.current_token(), token)
            # Cached: a second call within validity does not mint again.
            self.assertEqual(onemap_auth.current_token(), token)
            self.assertEqual(post.call_count, 1)

    def test_remints_when_near_expiry(self):
        os.environ["ONEMAP_EMAIL"] = "a@b.com"
        os.environ["ONEMAP_PASSWORD"] = "pw"
        nearly_expired = _fake_jwt(time.time() + 60)   # inside the refresh skew
        fresh = _fake_jwt(time.time() + 3 * 86400)
        with mock.patch("requests.post", side_effect=[_resp(nearly_expired), _resp(fresh)]) as post:
            self.assertEqual(onemap_auth.current_token(), nearly_expired)
            # Near-expiry token triggers a re-mint on the next call.
            self.assertEqual(onemap_auth.current_token(), fresh)
            self.assertEqual(post.call_count, 2)

    def test_refresh_forces_new_mint(self):
        os.environ["ONEMAP_EMAIL"] = "a@b.com"
        os.environ["ONEMAP_PASSWORD"] = "pw"
        t1 = _fake_jwt(time.time() + 3 * 86400)
        t2 = _fake_jwt(time.time() + 3 * 86400)
        with mock.patch("requests.post", side_effect=[_resp(t1), _resp(t2)]):
            self.assertEqual(onemap_auth.current_token(), t1)
            self.assertEqual(onemap_auth.refresh(), t2)

    def test_refresh_without_credentials_returns_static(self):
        os.environ["ONEMAP_TOKEN"] = _fake_jwt(time.time() + 3 * 86400)
        # No creds: refresh can't mint, returns the static token rather than failing.
        self.assertEqual(onemap_auth.refresh(), os.environ["ONEMAP_TOKEN"])

    def test_credentials_preferred_over_static(self):
        os.environ["ONEMAP_TOKEN"] = "static-token"
        os.environ["ONEMAP_EMAIL"] = "a@b.com"
        os.environ["ONEMAP_PASSWORD"] = "pw"
        minted = _fake_jwt(time.time() + 3 * 86400)
        with mock.patch("requests.post", return_value=_resp(minted)):
            self.assertEqual(onemap_auth.current_token(), minted)


if __name__ == "__main__":
    unittest.main()
