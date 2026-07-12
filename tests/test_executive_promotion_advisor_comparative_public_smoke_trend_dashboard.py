import unittest

from scripts.inject_executive_promotion_advisor_comparative_public_smoke_trend_card import (
    CARD_KEY,
    HOOK,
    inject,
)
from scripts.validate_executive_promotion_advisor_comparative_public_smoke_trend_card import validate


class ComparativeSmokeTrendDashboardTest(unittest.TestCase):
    def setUp(self):
        self.html = "<html><body><main></main></body></html>"
        self.runtime = {"production_ready": False, "cards": {}}
        self.state = {
            "cards": {
                CARD_KEY: {
                    "status": "READY",
                    "trend": "stable",
                    "mode": "report-only",
                    "production_blocker": False,
                    "human_approval_required": True,
                    "summary": {
                        "environment_count": 3,
                        "sample_count": 30,
                        "weighted_pass_rate_percent": 99.0,
                        "minimum_visual_consistency_percent": 98.0,
                        "minimum_stable_streak": 10,
                    },
                }
            }
        }

    def test_injects_and_validates_real_state(self):
        html, index = inject(self.html, self.runtime, self.state)
        validate(html, index)
        self.assertEqual(html.count(HOOK), 1)
        self.assertFalse(index["production_ready"])

    def test_is_idempotent(self):
        html, index = inject(self.html, self.runtime, self.state)
        html2, index2 = inject(html, index, self.state)
        self.assertEqual(html, html2)
        self.assertEqual(index, index2)

    def test_normalizes_unsafe_input(self):
        unsafe = {"cards": {CARD_KEY: {"mode": "blocking", "production_blocker": True}}}
        html, index = inject(self.html, self.runtime, unsafe)
        validate(html, index)
        card = index["cards"][CARD_KEY]
        self.assertEqual(card["mode"], "report-only")
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])

    def test_safe_fallback_when_evidence_missing(self):
        html, index = inject(self.html, self.runtime, {})
        validate(html, index)
        self.assertEqual(index["cards"][CARD_KEY]["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
