import unittest

from scripts.inject_executive_final_sync_history_public_smoke_trend_card import build_card, inject
from scripts.validate_executive_final_sync_history_public_smoke_trend_card import validate


class DashboardTrendCardTest(unittest.TestCase):
    def test_injects_valid_card(self):
        state = {"cards": {"executive_final_sync_history_public_smoke_trend": {
            "status": "eligible-for-human-review",
            "environment_coverage": "3/3",
            "samples": 9,
            "pass_rate": 100,
            "minimum_stable_sequence": 3,
            "eligible_for_human_review": True,
        }}}
        html = inject("<main></main>", build_card(state))
        self.assertEqual([], validate(html))
        self.assertIn("eligible-for-human-review", html)

    def test_is_idempotent(self):
        card = build_card({})
        once = inject("<main></main>", card)
        twice = inject(once, card)
        self.assertEqual(1, twice.count('id="executive-final-sync-history-public-smoke-trend"'))

    def test_fallback_is_safe(self):
        html = inject("<main></main>", build_card({}))
        self.assertIn("collecting-evidence", html)
        self.assertIn('data-production-blocker="false"', html)


if __name__ == "__main__":
    unittest.main()
