import unittest

from scripts.inject_user_experience_dashboard_executive_stability_card import CARD_ID, inject_card
from scripts.smoke_user_experience_dashboard_executive_stability_card import evaluate


VALUE = {
    "status": "UX_DASHBOARD_EXECUTIVE_STABILITY_STABLE",
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


class DashboardExecutiveStabilityCardTests(unittest.TestCase):
    def test_injection_is_idempotent(self):
        state = {"cards": {"user_experience_dashboard_executive_stability": VALUE}}
        first = inject_card({"cards": []}, state)
        second = inject_card(first, state)
        self.assertEqual(first, second)
        self.assertEqual(1, sum(card.get("id") == CARD_ID for card in second["cards"]))

    def test_fallback_preserves_guardrails(self):
        result = inject_card({"cards": []}, {})
        card = result["cards"][0]
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])
        self.assertEqual("report-only", card["mode"])

    def test_smoke_accepts_synchronized_sources(self):
        state = {"cards": {"user_experience_dashboard_executive_stability": VALUE}}
        brief = {"indicators": {"user_experience_dashboard_executive_stability": VALUE}}
        dashboard = {"cards": [{"id": CARD_ID, **VALUE}]}
        report = evaluate(state, brief, dashboard)
        self.assertTrue(report["synchronized"])
        self.assertEqual("UX_DASHBOARD_EXECUTIVE_STABILITY_CARD_OK", report["status"])

    def test_smoke_detects_drift(self):
        drifted = dict(VALUE, confidence_score=90)
        state = {"cards": {"user_experience_dashboard_executive_stability": VALUE}}
        brief = {"indicators": {"user_experience_dashboard_executive_stability": drifted}}
        dashboard = {"cards": [{"id": CARD_ID, **VALUE}]}
        report = evaluate(state, brief, dashboard)
        self.assertFalse(report["synchronized"])
        self.assertEqual("UX_DASHBOARD_EXECUTIVE_STABILITY_CARD_REVIEW", report["status"])


if __name__ == "__main__":
    unittest.main()
