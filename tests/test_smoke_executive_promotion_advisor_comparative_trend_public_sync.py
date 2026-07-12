import unittest

from scripts.smoke_executive_promotion_advisor_comparative_trend_public_sync import (
    CARD_KEY,
    append_history,
    validate_sync,
)


class ComparativeTrendPublicSyncTest(unittest.TestCase):
    def card(self):
        return {
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
            "trend": "stable",
            "weighted_pass_rate": 99.0,
        }

    def test_valid_and_synchronized(self):
        card = self.card()
        result = validate_sync(
            f'<section id="{CARD_KEY}"></section>',
            {"cards": {CARD_KEY: card}},
            {"cards": {CARD_KEY: card}},
        )
        self.assertEqual("PUBLIC_TREND_SMOKE_PASSED", result["status"])
        self.assertTrue(result["synchronized"])
        self.assertEqual([], result["issues"])

    def test_drift_is_review_only(self):
        runtime_card = self.card()
        brief_card = {**self.card(), "trend": "attention"}
        result = validate_sync(
            f'<section id="{CARD_KEY}"></section>',
            {"cards": {CARD_KEY: runtime_card}},
            {"cards": {CARD_KEY: brief_card}},
        )
        self.assertEqual("PUBLIC_TREND_SMOKE_REVIEW", result["status"])
        self.assertIn("state-brief-drift", result["issues"])
        self.assertFalse(result["production_blocker"])

    def test_unsafe_contract_is_review(self):
        unsafe = {**self.card(), "production_blocker": True}
        result = validate_sync(
            f'<section id="{CARD_KEY}"></section>',
            {"cards": {CARD_KEY: unsafe}},
            {"cards": {CARD_KEY: unsafe}},
        )
        self.assertEqual("PUBLIC_TREND_SMOKE_REVIEW", result["status"])
        self.assertIn("runtime-production-blocker-unsafe", result["issues"])

    def test_history_is_idempotent_and_segregated(self):
        result = {
            "status": "PUBLIC_TREND_SMOKE_PASSED",
            "synchronized": True,
            "issues": [],
        }
        history = append_history({}, "DEV", result)
        history = append_history(history, "DEV", result)
        history = append_history(history, "STG", result)
        self.assertEqual(1, history["environments"]["DEV"]["summary"]["samples"])
        self.assertEqual(1, history["environments"]["STG"]["summary"]["samples"])
        self.assertEqual(2, history["summary"]["environment_coverage"])

    def test_human_review_requires_all_environments_and_stability(self):
        history = {}
        for environment in ("DEV", "STG", "PROD"):
            for index in range(20):
                result = {
                    "status": "PUBLIC_TREND_SMOKE_PASSED",
                    "synchronized": True,
                    "issues": [str(index)],
                }
                history = append_history(history, environment, result)
        self.assertTrue(history["summary"]["eligible_for_human_review"])
        self.assertFalse(history["production_blocker"])
        self.assertTrue(history["human_approval_required"])


if __name__ == "__main__":
    unittest.main()
