import copy
import unittest

from scripts.inject_executive_sync_stability_index_card import CARD_ID, inject
from scripts.validate_executive_sync_stability_index_card import validate


class ExecutiveSyncStabilityIndexDashboardTests(unittest.TestCase):
    def setUp(self):
        self.runtime = {
            "production_ready": True,
            "cards": {
                "executive_sync_stability_index": {
                    "status": "stable",
                    "score": 98.4,
                    "environment_coverage": 100.0,
                    "total_samples": 90,
                    "weighted_pass_rate": 99.2,
                    "weighted_sync_rate": 98.8,
                    "minimum_stable_sequence": 24,
                    "mode": "report-only",
                    "production_blocker": False,
                    "human_approval_required": True,
                }
            },
        }

    def test_injects_and_validates_real_contract(self):
        html, runtime = inject("<main><!-- REQSYS_EXECUTIVE_SYNC_STABILITY_INDEX --></main>", copy.deepcopy(self.runtime))
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
        card = runtime["cards"]["executive_sync_stability_index"]
        self.assertEqual("insufficient-environment-coverage", card["status"])
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])
        self.assertEqual([], validate(html, runtime))

    def test_unsafe_input_is_normalized(self):
        runtime = copy.deepcopy(self.runtime)
        runtime["cards"]["executive_sync_stability_index"].update({
            "mode": "blocking",
            "production_blocker": True,
            "human_approval_required": False,
        })
        html, normalized = inject("<main></main>", runtime)
        card = normalized["cards"]["executive_sync_stability_index"]
        self.assertEqual("report-only", card["mode"])
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])
        self.assertEqual([], validate(html, normalized))


if __name__ == "__main__":
    unittest.main()
