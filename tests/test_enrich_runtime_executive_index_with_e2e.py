import unittest

from scripts.enrich_runtime_executive_index_with_e2e import enrich


class EnrichRuntimeExecutiveIndexWithE2ETests(unittest.TestCase):
    def indicator(self, status="E2E_CORRELATION_VERIFIED"):
        return {
            "contract": "reqsys-single-state-e2e-executive-indicator",
            "status": status,
            "mode": "advisory",
            "promotion_allowed": False,
            "human_approval_required": True,
            "metrics": {
                "confidence_score": 96,
                "production_readiness_score": 93,
                "operational_risk": "low",
            },
        }

    def test_verified_elevates_only_e2e_card(self):
        result = enrich({"summary": {}, "cards": {}}, self.indicator())
        self.assertTrue(result["cards"]["e2e_correlation"]["verified"])
        self.assertEqual(result["cards"]["e2e_correlation"]["confidence_score"], 96)
        self.assertFalse(result["summary"]["production_promotion_allowed"])
        self.assertTrue(result["summary"]["human_approval_required"])

    def test_pending_does_not_elevate_scores(self):
        result = enrich({"summary": {}, "cards": {}}, self.indicator("E2E_CORRELATION_PENDING"))
        card = result["cards"]["e2e_correlation"]
        self.assertFalse(card["verified"])
        self.assertEqual(card["confidence_score"], 0)
        self.assertEqual(card["production_readiness_score"], 0)

    def test_rejects_relaxed_guardrails(self):
        value = self.indicator()
        value["promotion_allowed"] = True
        with self.assertRaises(ValueError):
            enrich({}, value)

    def test_rejects_invalid_contract(self):
        value = self.indicator()
        value["contract"] = "invalid"
        with self.assertRaises(ValueError):
            enrich({}, value)


if __name__ == "__main__":
    unittest.main()
