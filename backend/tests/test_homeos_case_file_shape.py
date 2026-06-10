import os
import unittest
from unittest.mock import patch

from app.data.seed import build_seeded_repo
from app.homeos.pipeline import build_homeos_case_file


class TestCaseFileShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.homeos.wiring import setup as homeos_setup
        homeos_setup()
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=4, months=6)
        cls.block_id = cls.repo.blocks()[0].block_id

    def test_risks_are_strings_and_trace_present(self):
        with patch.dict(os.environ, {"HOMEOS_AGENT_MODE": "mock"}):
            cf = build_homeos_case_file(
                self.repo, "family with kids budget 500k near mrt", self.block_id
            )
        self.assertTrue(all(isinstance(r, str) for r in cf["evidence"]["risks"]))
        self.assertIn("trace", cf)
        self.assertEqual(cf["trace"], [])
        for item in cf["top_reasons"] + cf["top_watchouts"]:
            self.assertIn("source", item)


if __name__ == "__main__":
    unittest.main()
