import unittest

from scripts.enrich_runtime_executive_environment_promotion import enrich, summarize_environment_promotion


class RuntimeExecutiveEnvironmentPromotionTests(unittest.TestCase):
    def test_summarizes_ready_promotion_contract(self):
        payload = {
            "decision": "READY_FOR_PROD_PROMOTION",
            "ready_for_prod_promotion": True,
            "production_blockers": [],
            "coverage": {
                "required_environments": ["dev", "stg", "prod"],
                "ready_environments": ["dev", "stg", "prod"],
                "missing_environments": [],
                "failed_environments": [],
                "coverage_percent": 100,
            },
            "environments": [{"environment": "dev"}, {"environment": "stg"}, {"environment": "prod"}],
            "mode": "report_only",
        }

        card = summarize_environment_promotion(payload)

        self.assertTrue(card["available"])
        self.assertEqual(card["status"], "green")
        self.assertEqual(card["risk"], "low")
        self.assertTrue(card["ready_for_prod_promotion"])
        self.assertEqual(card["coverage_percent"], 100)

    def test_enrich_blocks_summary_when_promotion_not_ready(self):
        index = {"summary": {"production_ready": True, "status": "passed", "risk": "low"}, "cards": {}, "links": {}, "guardrails": []}
        readiness = {
            "decision": "BLOCKED_FOR_PROD_PROMOTION",
            "ready_for_prod_promotion": False,
            "production_blockers": ["env_stg_evidence_missing"],
            "coverage": {
                "required_environments": ["dev", "stg", "prod"],
                "ready_environments": ["dev"],
                "missing_environments": ["stg", "prod"],
                "failed_environments": [],
                "coverage_percent": 33.33,
            },
            "environments": [{"environment": "dev"}, {"environment": "stg"}, {"environment": "prod"}],
        }

        enriched = enrich(index, readiness)

        self.assertEqual(enriched["schema_version"], "1.3.0")
        self.assertFalse(enriched["summary"]["production_ready"])
        self.assertEqual(enriched["summary"]["status"], "critical")
        self.assertEqual(enriched["summary"]["risk"], "high")
        self.assertEqual(enriched["summary"]["environment_promotion_decision"], "BLOCKED_FOR_PROD_PROMOTION")
        self.assertIn("environment_promotion_readiness", enriched["cards"])
        self.assertEqual(enriched["links"]["environment_promotion_readiness"], "data/environment-promotion-readiness.json")
        self.assertIn("environment_promotion_readiness_required_before_prod_release", enriched["guardrails"])


if __name__ == "__main__":
    unittest.main()
