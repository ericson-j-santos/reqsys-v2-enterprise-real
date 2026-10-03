import unittest

from scripts.build_user_experience_dashboard_executive_stability import (
    REVIEW_STATUS,
    STABLE_STATUS,
    build,
)


class DashboardExecutiveStabilityTests(unittest.TestCase):
    def test_stable_history_is_eligible(self):
        history = [
            {"status": "UX_CONFIDENCE_DASHBOARD_RELIABILITY_CARD_OK", "drift": False, "fingerprint": "abc"}
            for _ in range(3)
        ]
        state = {"readiness": {"status": "unchanged"}, "production_ready": False}
        brief = {"title": "ReqSys"}

        indicator, out_state, out_brief = build(history, state, brief)

        self.assertEqual(STABLE_STATUS, indicator["status"])
        self.assertEqual(100.0, indicator["success_rate"])
        self.assertEqual(3, indicator["stable_sequence"])
        self.assertTrue(indicator["human_review_eligible"])
        self.assertEqual(state["readiness"], out_state["readiness"])
        self.assertFalse(out_state["production_ready"])
        self.assertIn("user_experience_dashboard_executive_stability", out_brief["indicators"])

    def test_recurring_drift_requires_review(self):
        history = [
            {"status": "UX_CONFIDENCE_DASHBOARD_RELIABILITY_CARD_OK", "drift": True, "fingerprint": "abc"},
            {"status": "UX_CONFIDENCE_DASHBOARD_RELIABILITY_CARD_OK", "drift": False, "fingerprint": "abc"},
            {"status": "UX_CONFIDENCE_DASHBOARD_RELIABILITY_CARD_OK", "drift": True, "fingerprint": "abc"},
        ]
        indicator, _, _ = build(history, {}, {})
        self.assertEqual(REVIEW_STATUS, indicator["status"])
        self.assertTrue(indicator["recurring_drift"])
        self.assertFalse(indicator["human_review_eligible"])

    def test_empty_history_is_safe(self):
        indicator, state, brief = build([], {}, {})
        self.assertEqual(REVIEW_STATUS, indicator["status"])
        self.assertEqual(0.0, indicator["success_rate"])
        self.assertEqual("report-only", indicator["mode"])
        self.assertFalse(indicator["production_blocker"])
        self.assertTrue(indicator["human_approval_required"])
        self.assertIn("cards", state)
        self.assertIn("indicators", brief)


if __name__ == "__main__":
    unittest.main()
