"""Tests for the block-agents lookup: address -> block -> agents with listings."""
import unittest

from tests.test_active_listings import make_block, make_listing


def _bidadari_block(block_id=164):
    return make_block(block_id=block_id, number="104A",
                      street="BIDADARI PK DR", postal="")


def _agent_listing(listing_id, phone, name="JOHN DOE",
                   agency="TBP PTE LTD", **kw):
    return make_listing(listing_id=listing_id, agent_phone=phone,
                        agent_name=name, agency_name=agency,
                        managed_by_agent=True, **kw)


class ParseAddressTest(unittest.TestCase):
    def test_splits_block_and_street(self):
        from app.services.block_agents import parse_address
        self.assertEqual(parse_address("104A Bidadari Pk Dr"),
                         ("104A", "Bidadari Pk Dr"))
        self.assertEqual(parse_address("  126a kim tian road "),
                         ("126A", "kim tian road"))

    def test_rejects_single_token(self):
        from app.services.block_agents import parse_address
        with self.assertRaises(ValueError):
            parse_address("104A")


class BlocksByNumberRepoTest(unittest.TestCase):
    def test_lookup_is_case_insensitive_and_exact(self):
        from app.repositories.memory import InMemoryRepository
        repo = InMemoryRepository()
        repo.add_blocks([_bidadari_block(), make_block(block_id=2, number="104")])
        found = repo.blocks_by_number("104a")
        self.assertEqual([b.block_id for b in found], [164])
        self.assertEqual(list(repo.blocks_by_number("999Z")), [])


class FindBlockAgentsTest(unittest.TestCase):
    def _repo(self):
        from app.repositories.memory import InMemoryRepository
        repo = InMemoryRepository()
        repo.add_blocks([_bidadari_block()])
        repo.add_active_listings([
            _agent_listing(1, "91234567", block_id=164, price=500000.0),
            _agent_listing(2, "91234567", block_id=164, price=700000.0),
            _agent_listing(3, "98765432", name="JANE DOE",
                           agency="TBP PTE LTD",
                           block_id=164, price=600000.0),
            make_listing(listing_id=4, block_id=164, price=550000.0),  # owner-listed
        ])
        return repo

    def test_groups_listings_by_agent(self):
        from app.services.block_agents import find_block_agents
        data = find_block_agents(self._repo(), "104A Bidadari Pk Dr")
        self.assertEqual(data["block"]["block_id"], 164)
        self.assertEqual(data["listing_count"], 4)
        agents = {a["agent_phone"]: a for a in data["agents"]}
        self.assertEqual(set(agents), {"91234567", "98765432"})
        self.assertEqual([l["listing_id"] for l in agents["91234567"]["listings"]],
                         [1, 2])
        self.assertEqual(len(data["owner_listings"]), 1)
        self.assertEqual(data["owner_listings"][0]["listing_id"], 4)

    def test_unabbreviated_street_still_matches(self):
        from app.services.block_agents import find_block_agents
        data = find_block_agents(self._repo(), "104A Bidadari Park Drive")
        self.assertIsNotNone(data)
        self.assertEqual(data["block"]["block_id"], 164)

    def test_unknown_block_returns_none(self):
        from app.services.block_agents import find_block_agents
        self.assertIsNone(find_block_agents(self._repo(), "999Z Nowhere St"))


class BlockAgentsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from app.api import deps
        from app.api.main import app
        from app.repositories.memory import InMemoryRepository

        repo = InMemoryRepository()
        repo.add_blocks([_bidadari_block()])
        repo.add_active_listings([
            _agent_listing(1, "91234567", block_id=164, price=500000.0),
            _agent_listing(2, "98765432", name="JANE DOE",
                           agency="TBP PTE LTD",
                           block_id=164, price=600000.0),
        ])
        app.dependency_overrides[deps.get_repository] = lambda: repo
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from app.api import deps
        from app.api.main import app
        app.dependency_overrides.pop(deps.get_repository, None)

    def test_returns_agents_for_address(self):
        resp = self.client.get("/blocks/agents",
                               params={"address": "104A Bidadari Pk Dr"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["block"]["block_number"], "104A")
        self.assertEqual(len(body["agents"]), 2)
        phones = {a["agent_phone"] for a in body["agents"]}
        self.assertEqual(phones, {"91234567", "98765432"})

    def test_404_for_unknown_address(self):
        resp = self.client.get("/blocks/agents",
                               params={"address": "1 Nowhere Lane"})
        self.assertEqual(resp.status_code, 404)

    def test_422_for_address_without_street(self):
        resp = self.client.get("/blocks/agents", params={"address": "104A"})
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
