import unittest
from unittest.mock import patch

from scripts.smoke_executive_promotion_advisor_comparative_public import append_history, smoke_public


class ComparativePublicSmokeTests(unittest.TestCase):
    @patch("scripts.smoke_executive_promotion_advisor_comparative_public._get_text")
    def test_valid_public_card_passes(self, get_text):
        get_text.side_effect = [
            '<section id="executive-promotion-advisor-public-smoke-comparison"></section>',
            '{"cards":{"executive_promotion_advisor_public_smoke_comparison":{"mode":"report-only","production_blocker":false,"human_approval_required":true}}}',
        ]
        result = smoke_public("https://example.test", "dev")
        self.assertTrue(result["passed"])
        self.assertEqual("PUBLIC_COMPARATIVE_SMOKE_PASSED", result["status"])
        self.assertFalse(result["production_blocker"])

    @patch("scripts.smoke_executive_promotion_advisor_comparative_public._get_text")
    def test_unsafe_contract_becomes_non_blocking_review(self, get_text):
        get_text.side_effect = [
            "executive-promotion-advisor-public-smoke-comparison",
            '{"cards":{"executive_promotion_advisor_public_smoke_comparison":{"mode":"blocking","production_blocker":true,"human_approval_required":false}}}',
        ]
        result = smoke_public("https://example.test", "stg")
        self.assertFalse(result["passed"])
        self.assertEqual("PUBLIC_COMPARATIVE_SMOKE_REVIEW", result["status"])
        self.assertFalse(result["production_blocker"])
        self.assertTrue(result["human_approval_required"])

    def test_history_is_segregated_and_idempotent(self):
        dev = {
            "environment": "dev",
            "checked_at": "2026-07-12T12:00:00+00:00",
            "url": "https://dev.test",
            "status": "PUBLIC_COMPARATIVE_SMOKE_PASSED",
            "passed": True,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        }
        stg = dict(dev, environment="stg", url="https://stg.test")
        history = append_history({}, dev)
        history = append_history(history, dev)
        history = append_history(history, stg)
        self.assertEqual(1, history["environments"]["dev"]["summary"]["sample_count"])
        self.assertEqual(1, history["environments"]["stg"]["summary"]["sample_count"])
        self.assertEqual(2, history["summary"]["environment_count"])
        self.assertFalse(history["summary"]["coverage_complete"])

    def test_eligibility_requires_real_history(self):
        history = {}
        for index in range(10):
            sample = {
                "environment": "prod",
                "checked_at": f"2026-07-12T12:{index:02d}:00+00:00",
                "url": "https://prod.test",
                "status": "PUBLIC_COMPARATIVE_SMOKE_PASSED",
                "passed": True,
            }
            history = append_history(history, sample)
        summary = history["environments"]["prod"]["summary"]
        self.assertEqual(10, summary["sample_count"])
        self.assertEqual(10, summary["stable_streak"])
        self.assertTrue(summary["eligible_for_human_review"])
        self.assertFalse(summary["production_blocker"])


if __name__ == "__main__":
    unittest.main()
