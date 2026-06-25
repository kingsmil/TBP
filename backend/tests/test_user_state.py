"""Tests for saved user state (Feature 1): auth gating + pure helpers.

The CRUD itself needs PostGIS, so here we assert the dev-bypass vs
production-required *gating* behaviour (which needs no DB) plus the pure
normalisation helpers.
"""
from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.services import user_state as svc

client = TestClient(app)


class AuthGating(unittest.TestCase):
    """Without a token: production requires auth (401); dev bypass lets the
    request through (so it reaches the engine check -> 503 in this DB-less test,
    proving auth did NOT block it)."""

    def setUp(self):
        self._saved = os.environ.get("AUTH_REQUIRED")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("AUTH_REQUIRED", None)
        else:
            os.environ["AUTH_REQUIRED"] = self._saved

    def test_production_requires_login(self):
        os.environ["AUTH_REQUIRED"] = "true"
        for path in ("/me/preferences", "/me/locations"):
            r = client.get(path)
            self.assertEqual(r.status_code, 401, path)

    def test_dev_bypass_passes_auth(self):
        os.environ["AUTH_REQUIRED"] = "false"
        r = client.get("/me/preferences")
        # Got past auth (not 401). No DB in tests -> 503, which is fine.
        self.assertNotEqual(r.status_code, 401)
        self.assertIn(r.status_code, (200, 503))

    def test_invalid_token_unauthorised_in_production(self):
        os.environ["AUTH_REQUIRED"] = "true"
        r = client.get("/me/preferences", headers={"Authorization": "Bearer not-a-jwt"})
        self.assertEqual(r.status_code, 401)


class PureHelpers(unittest.TestCase):
    def test_location_type_normalised(self):
        self.assertEqual(svc._normalise_type("home"), "home")
        self.assertEqual(svc._normalise_type("WORK"), "work")
        self.assertEqual(svc._normalise_type("partner"), "partner")
        self.assertEqual(svc._normalise_type("nonsense"), "custom")
        self.assertEqual(svc._normalise_type(None), "custom")

    def test_pref_fields_whitelist(self):
        # The columns the upsert is allowed to touch — guards against arbitrary keys.
        self.assertIn("commute_weight", svc.PREF_FIELDS)
        self.assertIn("preferred_private_property_types", svc.PREF_FIELDS)
        self.assertNotIn("user_id", svc.PREF_FIELDS)
        self.assertNotIn("metadata_json", svc.PREF_FIELDS)  # handled separately


if __name__ == "__main__":
    unittest.main()
