import unittest

from scripts.build_user_experience_environment_trend import build


def sample(**overrides):
    data = {
        "environment_coverage": ["DEV", "STG", "PROD"],
        "minimum_pass_rate": 100,
        "common_fingerprint": "abc123",
        "drift_detected": False,
        "sync_status": "UX_ENV_CARD_SYNC_OK",
    }
    data.update(overrides)
    return data


class UserExperienceEnvironmentTrendTests(unittest.TestCase):
    def test_three_healthy_samples_are_stable(self):
        result = build([sample(), sample(), sample()])
        self.assertEqual("UX_ENV_TREND_STABLE", result["status"])
        self.assertEqual(100, result["success_rate"])
        self.assertEqual(3, result["stable_sequence"])
        self.assertTrue(result["eligible_for_human_review"])

    def test_detects_recurring_drift(self):
        result = build([sample(drift_detected=True), sample(), sample(drift_detected=True)])
        self.assertTrue(result["recurring_drift"])
        self.assertEqual("UX_ENV_TREND_REVIEW", result["status"])

    def test_detects_degradation(self):
        result = build([sample(), sample(minimum_pass_rate=75)])
        self.assertTrue(result["degradation_detected"])
        self.assertFalse(result["eligible_for_human_review"])

    def test_empty_history_is_safe(self):
        result = build([])
        self.assertEqual(0, result["success_rate"])
        self.assertEqual("report-only", result["mode"])
        self.assertFalse(result["production_blocker"])
        self.assertTrue(result["human_approval_required"])


if __name__ == "__main__":
    unittest.main()
