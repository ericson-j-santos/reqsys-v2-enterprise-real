import unittest

from scripts.inject_executive_final_trend_sync_history_state_card import CARD_ID, inject
from scripts.validate_executive_final_trend_sync_history_state_card import validate


class FinalTrendSyncHistoryDashboardTests(unittest.TestCase):
    def test_injects_valid_card_and_is_idempotent(self):
        index = {
            "cards": {
                "executive_final_trend_sync_history_state": {
                    "status": "eligible-for-human-review",
                    "environment_coverage": ["DEV", "STG", "PROD"],
                    "samples": {"DEV": 3, "STG": 3, "PROD": 3},
                    "pass_rate": 100,
                    "stable_sequence": 3,
                    "common_fingerprint": "abc123",
                    "eligible_for_human_review": True,
                }
            }
        }
        dashboard = {"cards": []}
        inject(index, dashboard)
        inject(index, dashboard)
        self.assertEqual(1, len([c for c in dashboard["cards"] if c["id"] == CARD_ID]))
        self.assertEqual([], validate(dashboard))

    def test_missing_evidence_uses_safe_fallback(self):
        dashboard = {"cards": []}
        inject({"cards": {}}, dashboard)
        card = dashboard["cards"][0]
        self.assertEqual("collecting-evidence", card["status"])
        self.assertFalse(card["eligible_for_human_review"])
        self.assertEqual([], validate(dashboard))

    def test_rejects_unsafe_eligibility(self):
        dashboard = {
            "cards": [{
                "id": CARD_ID,
                "mode": "report-only",
                "production_blocker": False,
                "human_approval_required": True,
                "eligible_for_human_review": True,
                "environment_coverage": ["DEV"],
                "pass_rate": 90,
                "stable_sequence": 1,
                "common_fingerprint": None,
            }]
        }
        self.assertGreaterEqual(len(validate(dashboard)), 4)


if __name__ == "__main__":
    unittest.main()
