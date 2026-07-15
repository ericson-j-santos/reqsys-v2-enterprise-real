import unittest

from scripts.build_empty_state_recovery_trend import CARD_ID, consolidate, evaluate


class EmptyStateRecoveryTrendTests(unittest.TestCase):
    def test_measures_recovery_time_and_ux_100_criteria(self):
        events = []
        for index in range(5):
            minute = index * 2
            events.extend([
                {"context": "govbi-results", "event": "view", "occurredAt": f"2026-07-15T10:{minute:02d}:00Z"},
                {"context": "govbi-results", "event": "primary_action", "occurredAt": f"2026-07-15T10:{minute:02d}:20Z"},
            ])
        report = evaluate(events)
        self.assertEqual(report["recovery_rate"], 100.0)
        self.assertEqual(report["average_recovery_seconds"], 20.0)
        self.assertTrue(report["ux_100_ready"])
        self.assertEqual(report["status"], "UX_100_EVIDENCE_READY")
        self.assertFalse(report["production_blocker"])

    def test_safe_fallback_without_evidence(self):
        report = evaluate([])
        self.assertEqual(report["recovery_rate"], 0.0)
        self.assertFalse(report["ux_100_ready"])
        self.assertEqual(report["mode"], "advisory")

    def test_idempotent_dashboard_and_history_limit(self):
        report = evaluate([
            {"context": "dashboard", "event": "view", "occurredAt": "2026-07-15T10:00:00Z"},
            {"context": "dashboard", "event": "secondary_action", "occurredAt": "2026-07-15T10:00:10Z"},
        ])
        dashboard, history = consolidate(
            {"cards": [{"id": CARD_ID, "status": "old"}, {"id": "other"}]},
            [{"generated_at": str(i)} for i in range(35)],
            report,
        )
        self.assertEqual(sum(1 for card in dashboard["cards"] if card.get("id") == CARD_ID), 1)
        self.assertEqual(len(history), 30)
        self.assertEqual(history[-1]["recovery_rate"], 100.0)


if __name__ == "__main__":
    unittest.main()
