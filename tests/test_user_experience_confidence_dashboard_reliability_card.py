import unittest

from scripts.inject_user_experience_confidence_dashboard_reliability_card import CARD_ID, inject_card
from scripts.smoke_user_experience_confidence_dashboard_reliability_card import evaluate


class ConfidenceDashboardReliabilityCardTests(unittest.TestCase):
    def indicator(self):
        return {
            "status": "UX_CONFIDENCE_CARD_AVAILABILITY_STABLE",
            "availability_rate": 100.0,
            "stable_sequence": 3,
            "sample_count": 3,
            "confidence_score": 100,
            "common_fingerprint": "abc",
            "recurring_drift": False,
            "human_review_eligible": True,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        }

    def test_injection_is_idempotent(self):
        dashboard = {"cards": [{"id": CARD_ID, "status": "old"}]}
        once = inject_card(dashboard, self.indicator())
        twice = inject_card(once, self.indicator())
        self.assertEqual(1, len([c for c in twice["cards"] if c["id"] == CARD_ID]))
        self.assertEqual(100, twice["cards"][0]["confidence_score"])

    def test_fallback_is_safe(self):
        card = inject_card({"cards": []}, None)["cards"][0]
        self.assertFalse(card["human_review_eligible"])
        self.assertEqual("report-only", card["mode"])
        self.assertFalse(card["production_blocker"])

    def test_smoke_accepts_synchronized_sources(self):
        value = self.indicator()
        state = {"cards": {"user_experience_sync_confidence_availability": value}}
        brief = {"indicators": {"user_experience_sync_confidence_availability": value}}
        dashboard = inject_card({"cards": []}, value)
        result = evaluate(state, brief, dashboard)
        self.assertTrue(result["synchronized"])
        self.assertEqual("UX_CONFIDENCE_DASHBOARD_RELIABILITY_CARD_OK", result["status"])

    def test_smoke_detects_drift(self):
        value = self.indicator()
        state = {"cards": {"user_experience_sync_confidence_availability": value}}
        brief_value = dict(value, confidence_score=80)
        brief = {"indicators": {"user_experience_sync_confidence_availability": brief_value}}
        dashboard = inject_card({"cards": []}, value)
        result = evaluate(state, brief, dashboard)
        self.assertFalse(result["synchronized"])
        self.assertEqual("UX_CONFIDENCE_DASHBOARD_RELIABILITY_CARD_REVIEW", result["status"])


if __name__ == "__main__":
    unittest.main()
