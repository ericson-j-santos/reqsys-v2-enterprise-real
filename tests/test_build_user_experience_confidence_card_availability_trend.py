import copy
import unittest

from scripts.build_user_experience_confidence_card_availability_trend import build, consolidate


class ConfidenceCardAvailabilityTrendTests(unittest.TestCase):
    def test_marks_stable_after_three_healthy_samples(self):
        samples = [
            {"available": True, "synced": True, "fingerprint": "abc", "drift_detected": False},
            {"available": True, "synced": True, "fingerprint": "abc", "drift_detected": False},
            {"available": True, "synced": True, "fingerprint": "abc", "drift_detected": False},
        ]
        report = build(samples)
        self.assertEqual(report["status"], "UX_CONFIDENCE_CARD_AVAILABILITY_STABLE")
        self.assertEqual(report["availability_rate"], 100.0)
        self.assertEqual(report["stable_sequence"], 3)
        self.assertEqual(report["confidence_level"], "HIGH")
        self.assertTrue(report["human_review_eligible"])

    def test_recurring_drift_requires_review(self):
        samples = [
            {"available": True, "synced": True, "fingerprint": "abc", "drift_detected": True},
            {"available": True, "synced": True, "fingerprint": "abc", "drift_detected": False},
            {"available": True, "synced": True, "fingerprint": "abc", "drift_detected": True},
        ]
        report = build(samples)
        self.assertTrue(report["recurring_drift"])
        self.assertFalse(report["human_review_eligible"])
        self.assertEqual(report["status"], "UX_CONFIDENCE_CARD_AVAILABILITY_REVIEW")

    def test_empty_history_is_safe(self):
        report = build([])
        self.assertEqual(report["availability_rate"], 0.0)
        self.assertEqual(report["confidence_level"], "LOW")
        self.assertFalse(report["production_blocker"])
        self.assertTrue(report["human_approval_required"])

    def test_consolidation_preserves_readiness_and_production_ready(self):
        state = {"readiness": {"status": "unchanged"}, "production_ready": False}
        brief = {"production_ready": False}
        before_state = copy.deepcopy(state)
        before_brief = copy.deepcopy(brief)
        history = {"samples": [
            {"available": True, "synced": True, "fingerprint": "abc", "drift_detected": False},
            {"available": True, "synced": True, "fingerprint": "abc", "drift_detected": False},
            {"available": True, "synced": True, "fingerprint": "abc", "drift_detected": False},
        ]}
        _, state_out, brief_out = consolidate(history, state, brief)
        self.assertEqual(state_out["readiness"], before_state["readiness"])
        self.assertEqual(state_out["production_ready"], before_state["production_ready"])
        self.assertEqual(brief_out["production_ready"], before_brief["production_ready"])
        self.assertIn("user_experience_sync_confidence_availability", state_out["cards"])
        self.assertIn("user_experience_sync_confidence_availability", brief_out["indicators"])


if __name__ == "__main__":
    unittest.main()
