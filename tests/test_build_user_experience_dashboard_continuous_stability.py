import copy
import unittest

from scripts.build_user_experience_dashboard_continuous_stability import (
    REVIEW,
    STABLE,
    build,
    consolidate,
)


class DashboardContinuousStabilityTests(unittest.TestCase):
    def healthy(self, fingerprint="stable-contract"):
        return {
            "classification": "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK",
            "synchronized": True,
            "guardrails_ok": True,
            "card_count": 1,
            "fingerprint": fingerprint,
        }

    def test_marks_stable_after_three_healthy_samples(self):
        result = build({"samples": [self.healthy(), self.healthy(), self.healthy()]})
        self.assertEqual(STABLE, result["status"])
        self.assertEqual(100.0, result["success_rate"])
        self.assertEqual(3, result["stable_sequence"])
        self.assertEqual(100, result["confidence_score"])
        self.assertTrue(result["human_review_eligible"])

    def test_recurring_failure_requires_review(self):
        failed = dict(self.healthy(), synchronized=False)
        result = build([failed, self.healthy(), failed])
        self.assertEqual(REVIEW, result["status"])
        self.assertTrue(result["recurring_drift"])
        self.assertFalse(result["human_review_eligible"])

    def test_fingerprint_divergence_requires_review(self):
        result = build([self.healthy("a"), self.healthy("b"), self.healthy("a")])
        self.assertEqual(REVIEW, result["status"])
        self.assertIsNone(result["common_fingerprint"])

    def test_empty_history_is_safe(self):
        result = build([])
        self.assertEqual(REVIEW, result["status"])
        self.assertEqual("report-only", result["mode"])
        self.assertFalse(result["production_blocker"])
        self.assertTrue(result["human_approval_required"])

    def test_consolidation_preserves_production_contract(self):
        state = {"readiness": {"status": "preserved"}, "production_ready": False}
        brief = {"production_ready": False}
        before_state = copy.deepcopy(state)
        before_brief = copy.deepcopy(brief)
        _, state_out, brief_out = consolidate(
            [self.healthy(), self.healthy(), self.healthy()], state, brief
        )
        self.assertEqual(before_state["readiness"], state_out["readiness"])
        self.assertEqual(before_state["production_ready"], state_out["production_ready"])
        self.assertEqual(before_brief["production_ready"], brief_out["production_ready"])
        self.assertIn("user_experience_dashboard_continuous_stability", state_out["cards"])
        self.assertIn("user_experience_dashboard_continuous_stability", brief_out["indicators"])


if __name__ == "__main__":
    unittest.main()
