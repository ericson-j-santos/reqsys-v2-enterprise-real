import unittest

from scripts.build_empty_state_telemetry_indicator import CARD_ID, KEY, consolidate, evaluate


class EmptyStateTelemetryIndicatorTests(unittest.TestCase):
    def test_stable_indicator_with_recovery(self):
        indicator = evaluate([
            {"context": "govbi-results", "event": "view"},
            {"context": "govbi-results", "event": "primary_action"},
            {"context": "dashboard", "event": "view"},
            {"context": "dashboard", "event": "secondary_action"},
            {"context": "dashboard", "event": "view"},
        ])
        self.assertEqual(indicator["status"], "UX_EMPTY_STATES_STABLE")
        self.assertEqual(indicator["views"], 3)
        self.assertEqual(indicator["recovery_rate"], 66.7)
        self.assertFalse(indicator["production_blocker"])

    def test_safe_fallback_without_evidence(self):
        indicator = evaluate([])
        self.assertEqual(indicator["status"], "UX_EMPTY_STATES_REVIEW")
        self.assertFalse(indicator["evidence_complete"])
        self.assertEqual(indicator["recovery_rate"], 0.0)

    def test_consolidates_without_duplicates(self):
        indicator = evaluate([{"context": "govbi-results", "event": "view"}])
        state, brief, dashboard = consolidate(
            {"indicators": {}},
            {"indicators": {}},
            {"cards": [{"id": CARD_ID, "status": "old"}, {"id": "other"}]},
            indicator,
        )
        self.assertEqual(state["indicators"][KEY], indicator)
        self.assertEqual(brief["indicators"][KEY], indicator)
        self.assertEqual(sum(1 for card in dashboard["cards"] if card.get("id") == CARD_ID), 1)
        self.assertEqual(len(dashboard["cards"]), 2)


if __name__ == "__main__":
    unittest.main()
