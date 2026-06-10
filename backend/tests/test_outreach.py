"""Tests for the WhatsApp outreach message agent, service, and API."""
import os
import unittest
from unittest import mock

from tests.test_active_listings import make_block, make_listing


class MockOutreachMessageTest(unittest.TestCase):
    def test_mock_message_references_unit_and_availability(self):
        from app.homeos.mock.agents import mock_outreach_message
        listing = make_listing()
        msg = mock_outreach_message(
            listing,
            avatar_summary="Young family, two kids, budget $1.4M.",
            contact_name="Sam",
            availability=["Sat 10-12am"],
        )
        self.assertIn("126A", msg)
        self.assertIn("4-Room", msg)
        self.assertIn("Sat 10-12am", msg)
        self.assertIn("Sam", msg)

    def test_mock_message_deterministic(self):
        from app.homeos.mock.agents import mock_outreach_message
        listing = make_listing()
        a = mock_outreach_message(listing, None, None, [])
        b = mock_outreach_message(listing, None, None, [])
        self.assertEqual(a, b)


class SanitizePhoneTest(unittest.TestCase):
    def test_strips_punctuation_and_prefixes_country_code(self):
        from app.services.outreach import sanitize_phone
        self.assertEqual(sanitize_phone("+65 9123-4567"), "6591234567")
        self.assertEqual(sanitize_phone("9123 4567"), "6591234567")
        self.assertEqual(sanitize_phone("6591234567"), "6591234567")

    def test_empty_returns_none(self):
        from app.services.outreach import sanitize_phone
        self.assertIsNone(sanitize_phone(None))
        self.assertIsNone(sanitize_phone(""))
        self.assertIsNone(sanitize_phone(" - "))


class PrepareOutreachTest(unittest.TestCase):
    def setUp(self):
        os.environ["HOMEOS_AGENT_MODE"] = "mock"
        from app.repositories.memory import InMemoryRepository
        self.repo = InMemoryRepository()
        self.repo.add_blocks([make_block()])

    def tearDown(self):
        os.environ.pop("HOMEOS_AGENT_MODE", None)

    def test_message_without_contact_has_no_channel_urls(self):
        from app.services.outreach import prepare_outreach_message
        self.repo.add_active_listings([make_listing()])
        out = prepare_outreach_message(self.repo, 40661)
        self.assertTrue(out["message"])
        self.assertNotIn("whatsapp_url", out)
        self.assertNotIn("email_url", out)

    def test_whatsapp_url_when_phone_present(self):
        from app.services.outreach import prepare_outreach_message
        self.repo.add_active_listings([
            make_listing(agent_phone="9123 4567", agent_name="Jane Tan")])
        out = prepare_outreach_message(self.repo, 40661, contact_name="Sam")
        self.assertTrue(out["whatsapp_url"].startswith("https://wa.me/6591234567?text="))
        self.assertEqual(out["agent_name"], "Jane Tan")

    def test_email_url_when_email_present(self):
        from app.services.outreach import prepare_outreach_message
        self.repo.add_active_listings([
            make_listing(agent_email="jane@agency.sg")])
        out = prepare_outreach_message(self.repo, 40661)
        self.assertTrue(out["email_url"].startswith("mailto:jane@agency.sg?"))

    def test_unknown_listing_raises(self):
        from app.services.outreach import prepare_outreach_message
        with self.assertRaises(ValueError):
            prepare_outreach_message(self.repo, 999)


class OutreachApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["HOMEOS_AGENT_MODE"] = "mock"
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.api.main import app
        from app.repositories.memory import InMemoryRepository

        repo = InMemoryRepository()
        repo.add_blocks([make_block()])
        repo.add_active_listings([
            make_listing(listing_id=1),
            make_listing(listing_id=2, agent_phone="91234567"),
        ])
        app.dependency_overrides[deps.get_repository] = lambda: repo
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("HOMEOS_AGENT_MODE", None)
        from app.api import deps
        from app.api.main import app
        app.dependency_overrides.pop(deps.get_repository, None)

    def test_prepare_returns_message(self):
        res = self.client.post("/listings/1/outreach-message", json={})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["message"])
        self.assertNotIn("whatsapp_url", body)

    def test_whatsapp_url_present_for_listing_with_phone(self):
        res = self.client.post(
            "/listings/2/outreach-message",
            json={"contact_name": "Sam", "availability": ["Sat 10-12am"]})
        self.assertEqual(res.status_code, 200)
        self.assertIn("wa.me/6591234567", res.json()["whatsapp_url"])

    def test_unknown_listing_404(self):
        res = self.client.post("/listings/999/outreach-message", json={})
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
