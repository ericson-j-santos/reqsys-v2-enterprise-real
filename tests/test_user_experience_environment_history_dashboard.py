import unittest

from scripts.inject_user_experience_environment_history_card import CARD_ID, inject
from scripts.smoke_user_experience_environment_history_card import smoke
from scripts.validate_user_experience_environment_history_card import validate


SOURCE = {
    "status": "eligible-for-human-review",
    "environment_coverage": ["DEV", "STG", "PROD"],
    "pass_rate_by_environment": {"DEV": 100, "STG": 100, "PROD": 100},
    "minimum_pass_rate": 100,
    "stable_sequence": 3,
    "common_fingerprint": "abc123",
    "drift_detected": False,
    "eligible_for_human_review": True,
    "mode": "report-only",
    "production_blocker": False,
    "human_approval_required": True,
}


class UserExperienceEnvironmentHistoryDashboardTests(unittest.TestCase):
    def test_publish_validate_and_smoke_are_idempotent(self):
        index = {"cards": {"user_experience_environment_history": dict(SOURCE)}}
        brief = {"indicators": {"user_experience_environment_history": dict(SOURCE)}}
        dashboard = {"cards": []}
        inject(index, dashboard)
        inject(index, dashboard)
        self.assertEqual(1, len([card for card in dashboard["cards"] if card["id"] == CARD_ID]))
        self.assertEqual([], validate(dashboard))
        result = smoke(index, brief, dashboard)
        self.assertEqual("UX_ENV_CARD_SYNC_OK", result["status"])
        self.assertTrue(result["card_available"])

    def test_missing_evidence_uses_safe_fallback(self):
        dashboard = {"cards": []}
        inject({"cards": {}}, dashboard)
        card = dashboard["cards"][0]
        self.assertEqual("collecting-evidence", card["status"])
        self.assertFalse(card["eligible_for_human_review"])
        self.assertEqual([], validate(dashboard))

    def test_detects_drift_between_sources(self):
        index = {"cards": {"user_experience_environment_history": dict(SOURCE)}}
        brief_source = dict(SOURCE)
        brief_source["minimum_pass_rate"] = 75
        brief = {"indicators": {"user_experience_environment_history": brief_source}}
        dashboard = {"cards": []}
        inject(index, dashboard)
        result = smoke(index, brief, dashboard)
        self.assertEqual("UX_ENV_CARD_SYNC_REVIEW", result["status"])
        self.assertFalse(result["synchronized"])

    def test_rejects_unsafe_eligibility(self):
        dashboard = {"cards": [{
            "id": CARD_ID,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
            "eligible_for_human_review": True,
            "environment_coverage": ["DEV"],
            "minimum_pass_rate": 80,
            "stable_sequence": 1,
            "common_fingerprint": None,
            "drift_detected": True,
        }]}
        self.assertGreaterEqual(len(validate(dashboard)), 5)


if __name__ == "__main__":
    unittest.main()
