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

    def test_lifestyle_none_does_not_change_score(self):
        score_no_ls, _, _ = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {})
        score_with_none, _, _ = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {}, lifestyle=None)
        self.assertEqual(score_no_ls, score_with_none)

    def test_strong_lifestyle_adds_points(self):
        score_base, _, _ = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {})
        score_ls, _, _ = worth_viewing_score(
            _MARKET_WITHIN, _LOCATION_MRT, _RISK, {},
            lifestyle={"lifestyle_score": 80, "watchouts": []},
        )
        self.assertGreater(score_ls, score_base)

    def test_strong_lifestyle_adds_reason_attributed_to_lifestyle(self):
        _, reasons, _ = worth_viewing_score(
            _MARKET_WITHIN, _LOCATION_MRT, _RISK, {},
            lifestyle={"lifestyle_score": 80, "watchouts": []},
        )
        ls_reasons = [r for r in reasons if r["source"] == "lifestyle"]
        self.assertGreater(len(ls_reasons), 0)

    def test_weak_lifestyle_adds_watchout_attributed_to_lifestyle(self):
        _, _, watchouts = worth_viewing_score(
            _MARKET_WITHIN, _LOCATION_MRT, _RISK, {},
            lifestyle={"lifestyle_score": 30, "watchouts": []},
        )
        ls_watchouts = [w for w in watchouts if w["source"] == "lifestyle"]
        self.assertGreater(len(ls_watchouts), 0)

    def test_lifestyle_watchouts_propagate_to_scoring(self):
        _, _, watchouts = worth_viewing_score(
            _MARKET_WITHIN, _LOCATION_MRT, _RISK, {},
            lifestyle={"lifestyle_score": 60, "watchouts": ["Commute burden is high."]},
        )
        texts = item_texts(watchouts)
        self.assertTrue(any("Commute burden" in t for t in texts))

    def test_lifestyle_source_in_attributed_items(self):
        _, reasons, watchouts = worth_viewing_score(
            _MARKET_WITHIN, _LOCATION_MRT, _RISK, {},
            lifestyle={"lifestyle_score": 80, "watchouts": ["Commute burden is high."]},
        )
        sources = {item["source"] for item in reasons + watchouts}
        self.assertIn("lifestyle", sources)


if __name__ == "__main__":
    unittest.main()
