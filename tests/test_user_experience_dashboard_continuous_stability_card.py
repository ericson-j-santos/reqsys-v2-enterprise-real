import unittest

from scripts.inject_user_experience_dashboard_continuous_stability_card import CARD_ID, inject
from scripts.smoke_user_experience_dashboard_continuous_stability_card import evaluate


VALUE = {
    "status": "UX_DASHBOARD_CONTINUOUS_STABILITY_STABLE",
    "success_rate": 100.0,
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


class ContinuousStabilityCardTests(unittest.TestCase):
    def test_injection_is_idempotent(self):
        first = inject({"cards": []}, VALUE)
        second = inject(first, VALUE)
        matches = [item for item in second["cards"] if item.get("id") == CARD_ID]
        self.assertEqual(1, len(matches))
        self.assertEqual(100, matches[0]["confidence_score"])

    def test_fallback_is_safe(self):
        card = inject({}, None)["cards"][0]
        self.assertEqual("UX_DASHBOARD_CONTINUOUS_STABILITY_REVIEW", card["status"])
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])
        self.assertFalse(card["human_review_eligible"])

    def test_smoke_accepts_synchronized_sources(self):
        state = {"cards": {"user_experience_dashboard_continuous_stability": VALUE}}
        brief = {"indicators": {"user_experience_dashboard_continuous_stability": VALUE}}
        dashboard = inject({"cards": []}, VALUE)
        result = evaluate(state, brief, dashboard)
        self.assertEqual("UX_DASHBOARD_CONTINUOUS_STABILITY_CARD_OK", result["status"])
        self.assertTrue(result["synchronized"])

    def test_smoke_detects_drift(self):
        state = {"cards": {"user_experience_dashboard_continuous_stability": VALUE}}
        brief = {"indicators": {"user_experience_dashboard_continuous_stability": dict(VALUE, confidence_score=80)}}
        dashboard = inject({"cards": []}, VALUE)
        result = evaluate(state, brief, dashboard)
        self.assertEqual("UX_DASHBOARD_CONTINUOUS_STABILITY_CARD_REVIEW", result["status"])
        self.assertFalse(result["synchronized"])


if __name__ == "__main__":
    unittest.main()
