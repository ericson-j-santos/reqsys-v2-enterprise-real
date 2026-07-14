import unittest
from scripts.build_user_experience_dashboard_continuous_stability_trend import build, consolidate, STABLE, REVIEW


class ContinuousStabilityTrendTests(unittest.TestCase):
    def test_stable_after_three_synced_samples(self):
        history = {"samples": [
            {"status": "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK", "fingerprint": "abc", "drift_detected": False},
            {"status": "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK", "fingerprint": "abc", "drift_detected": False},
            {"status": "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK", "fingerprint": "abc", "drift_detected": False},
        ]}
        result = build(history)
        self.assertEqual(STABLE, result["status"])
        self.assertEqual(100.0, result["success_rate"])
        self.assertEqual(3, result["stable_streak"])
        self.assertTrue(result["human_review_eligible"])

    def test_recurring_drift_requires_review(self):
        history = {"samples": [
            {"status": "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK", "fingerprint": "abc", "drift_detected": True},
            {"status": "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK", "fingerprint": "abc", "drift_detected": True},
            {"status": "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK", "fingerprint": "abc", "drift_detected": False},
        ]}
        result = build(history)
        self.assertEqual(REVIEW, result["status"])
        self.assertTrue(result["recurring_drift"])
        self.assertFalse(result["human_review_eligible"])

    def test_empty_history_is_safe_and_preserves_readiness(self):
        state = {"readiness": "READY", "production_ready": False}
        executive = {"readiness": "READY", "production_ready": False}
        state_out, executive_out, indicator = consolidate({"samples": []}, state, executive)
        self.assertEqual(REVIEW, indicator["status"])
        self.assertEqual("READY", state_out["readiness"])
        self.assertFalse(state_out["production_ready"])
        self.assertEqual("READY", executive_out["readiness"])
        self.assertFalse(executive_out["production_ready"])
        self.assertFalse(indicator["guardrails"]["deploy_changed"])


if __name__ == "__main__":
    unittest.main()
