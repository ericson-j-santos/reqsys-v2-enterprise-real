import copy
import unittest

from scripts.inject_executive_final_sync_history_state_card import CARD_ID, CARD_KEY, inject
from scripts.validate_executive_final_sync_history_state_card import validate


class ExecutiveFinalSyncHistoryStateDashboardTest(unittest.TestCase):
    def setUp(self):
        self.runtime = {
            "production_ready": True,
            "cards": {
                CARD_KEY: {
                    "status": "eligible-for-human-review",
                    "coverage_complete": True,
                    "synchronized": True,
                    "total_samples": 12,
                    "weighted_pass_rate_percent": 100.0,
                    "minimum_stable_sequence": 4,
                    "common_fingerprint": "abc123def456",
                    "eligible_for_human_review": True,
                    "environments": {"dev": {}, "stg": {}, "prod": {}},
                    "mode": "report-only",
                    "production_blocker": False,
                    "human_approval_required": True,
                }
            },
        }

    def test_injects_and_validates_contract(self):
        html, runtime = inject("<main></main>", copy.deepcopy(self.runtime))
        self.assertIn(f'id="{CARD_ID}"', html)
        self.assertEqual([], validate(html, runtime))
        self.assertTrue(runtime["production_ready"])

    def test_is_idempotent(self):
        html, runtime = inject("<main></main>", copy.deepcopy(self.runtime))
        html2, runtime2 = inject(html, runtime)
        self.assertEqual(1, html2.count(f'id="{CARD_ID}"'))
        self.assertEqual([], validate(html2, runtime2))

    def test_missing_evidence_uses_safe_fallback(self):
        html, runtime = inject("<main></main>", {"production_ready": False})
        card = runtime["cards"][CARD_KEY]
        self.assertEqual("insufficient-environment-coverage", card["status"])
        self.assertFalse(card["eligible_for_human_review"])
        self.assertFalse(card["production_blocker"])
        self.assertEqual([], validate(html, runtime))

    def test_unsafe_input_is_normalized(self):
        runtime = copy.deepcopy(self.runtime)
        runtime["cards"][CARD_KEY].update({
            "mode": "blocking",
            "production_blocker": True,
            "human_approval_required": False,
        })
        html, normalized = inject("<main></main>", runtime)
        card = normalized["cards"][CARD_KEY]
        self.assertEqual("report-only", card["mode"])
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])
        self.assertEqual([], validate(html, normalized))

    def test_rejects_unsafe_eligibility(self):
        html, runtime = inject("<main></main>", copy.deepcopy(self.runtime))
        runtime["cards"][CARD_KEY]["common_fingerprint"] = ""
        errors = validate(html, runtime)
        self.assertIn("eligibility requires common fingerprint", errors)


if __name__ == "__main__":
    unittest.main()
