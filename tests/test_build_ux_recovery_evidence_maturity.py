import unittest

from scripts.build_ux_recovery_evidence_maturity import CARD_ID, evaluate, publish_dashboard


class UXRecoveryEvidenceMaturityTests(unittest.TestCase):
    def test_distinguishes_synthetic_only(self):
        indicator = evaluate([
            {"evidence_source": "synthetic", "recovery_rate": 100, "average_recovery_seconds": 10, "ux_100_ready": True},
        ])
        self.assertEqual(indicator["status"], "UX_EVIDENCE_SYNTHETIC_ONLY")
        self.assertFalse(indicator["gold_ready"])

    def test_marks_gold_only_with_runtime_history(self):
        history = [
            {
                "evidence_source": "runtime",
                "recovery_rate": 80,
                "average_recovery_seconds": 20,
                "ux_100_ready": index < 3,
            }
            for index in range(5)
        ]
        indicator = evaluate(history)
        self.assertEqual(indicator["status"], "UX_EVIDENCE_GOLD_READY")
        self.assertTrue(indicator["gold_ready"])
        self.assertFalse(indicator["production_blocker"])

    def test_publishes_idempotent_card(self):
        indicator = evaluate([])
        dashboard = publish_dashboard({"cards": [{"id": CARD_ID}, {"id": "other"}]}, indicator)
        self.assertEqual(sum(1 for card in dashboard["cards"] if card.get("id") == CARD_ID), 1)
        self.assertEqual(len(dashboard["cards"]), 2)


if __name__ == "__main__":
    unittest.main()
