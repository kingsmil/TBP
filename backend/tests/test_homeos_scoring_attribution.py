import unittest

from app.homeos.scoring import worth_viewing_score, item_texts

_MARKET_WITHIN = {"budget_signal": "within_budget", "transaction_count": 6}
_LOCATION_MRT = {"connections": [{"type": "mrt", "signal": "strong"}]}
_RISK = {"watchouts": ["Lease decay risk noted."], "score_adjustment": 0.0}


class TestScoringAttribution(unittest.TestCase):
    def test_reasons_and_watchouts_are_attributed_items(self):
        score, reasons, watchouts = worth_viewing_score(
            _MARKET_WITHIN, _LOCATION_MRT, _RISK, {}
        )
        for item in reasons + watchouts:
            self.assertIn("text", item)
            self.assertIn("source", item)
            self.assertIn(item["source"], {"market", "location", "risk"})

    def test_budget_reason_from_market(self):
        _, reasons, _ = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {})
        budget = next(r for r in reasons if "budget" in r["text"].lower())
        self.assertEqual(budget["source"], "market")

    def test_mrt_reason_from_location(self):
        _, reasons, _ = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {})
        mrt = next(r for r in reasons if "MRT" in r["text"])
        self.assertEqual(mrt["source"], "location")

    def test_seed_watchout_from_risk(self):
        _, _, watchouts = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {})
        seeded = next(w for w in watchouts if "Lease decay" in w["text"])
        self.assertEqual(seeded["source"], "risk")

    def test_item_texts_extracts_plain_strings(self):
        _, reasons, _ = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {})
        texts = item_texts(reasons)
        self.assertTrue(all(isinstance(t, str) for t in texts))


if __name__ == "__main__":
    unittest.main()
