import unittest

from scripts.build_user_experience_dashboard_continuous_reliability import REVIEW, STABLE, build


class DashboardContinuousReliabilityTests(unittest.TestCase):
    def test_stable_after_three_healthy_samples(self):
        sample = {
            "status": "UX_DASHBOARD_EXECUTIVE_STABILITY_CARD_OK",
            "guardrails_ok": True,
            "drift": False,
            "fingerprint": "same",
        }
        result = build([sample, sample, sample])
        self.assertEqual(STABLE, result["status"])
        self.assertEqual(100.0, result["success_rate"])
        self.assertEqual(3, result["stable_sequence"])
        self.assertTrue(result["eligible_for_human_review"])

    def test_recurrent_drift_requires_review(self):
        history = [
            {"status": "UX_DASHBOARD_EXECUTIVE_STABILITY_CARD_OK", "guardrails_ok": True, "drift": True},
            {"status": "UX_DASHBOARD_EXECUTIVE_STABILITY_CARD_OK", "guardrails_ok": True, "drift": True},
            {"status": "UX_DASHBOARD_EXECUTIVE_STABILITY_CARD_OK", "guardrails_ok": True, "drift": False},
        ]
        result = build(history)
        self.assertEqual(REVIEW, result["status"])
        self.assertTrue(result["recurrent_drift"])
        self.assertFalse(result["eligible_for_human_review"])

    def test_empty_history_is_safe(self):
        result = build([])
        self.assertEqual(REVIEW, result["status"])
        self.assertEqual("report-only", result["mode"])
        self.assertFalse(result["production_blocker"])
        self.assertTrue(result["human_approval_required"])


if __name__ == "__main__":
    unittest.main()
