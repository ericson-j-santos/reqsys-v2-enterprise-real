import unittest

from scripts.build_user_experience_sync_confidence import build, consolidate


class SyncConfidenceTests(unittest.TestCase):
    def test_high_confidence_after_three_healthy_samples(self):
        samples = [
            {"status": "UX_PUBLIC_AVAILABILITY_SYNC_OK", "drift_detected": False}
            for _ in range(3)
        ]
        result = build(samples)
        self.assertEqual(result["confidence_level"], "HIGH")
        self.assertEqual(result["sync_rate_percent"], 100.0)
        self.assertEqual(result["stable_streak"], 3)
        self.assertTrue(result["human_review_eligible"])

    def test_recurring_drift_forces_review(self):
        samples = [
            {"status": "UX_PUBLIC_AVAILABILITY_SYNC_OK", "drift_detected": False},
            {"status": "UX_PUBLIC_AVAILABILITY_SYNC_REVIEW", "drift_detected": True},
            {"status": "UX_PUBLIC_AVAILABILITY_SYNC_REVIEW", "drift_detected": True},
        ]
        result = build(samples)
        self.assertTrue(result["recurring_drift"])
        self.assertEqual(result["confidence_level"], "LOW")
        self.assertFalse(result["human_review_eligible"])

    def test_empty_history_is_safe(self):
        result = build([])
        self.assertEqual(result["confidence_score"], 0)
        self.assertEqual(result["status"], "UX_SYNC_CONFIDENCE_REVIEW")
        self.assertFalse(result["production_blocker"])

    def test_consolidates_without_changing_production_flags(self):
        payload = {
            "samples": [
                {"status": "UX_PUBLIC_AVAILABILITY_SYNC_OK", "drift_detected": False}
                for _ in range(3)
            ],
            "state": {"readiness": "unchanged", "production_ready": False},
            "executive_brief": {},
        }
        result = consolidate(payload)
        self.assertEqual(result["state"]["readiness"], "unchanged")
        self.assertFalse(result["state"]["production_ready"])
        self.assertIn("user_experience_sync_confidence", result["state"]["cards"])
        self.assertIn("user_experience_sync_confidence", result["executive_brief"]["indicators"])


if __name__ == "__main__":
    unittest.main()
