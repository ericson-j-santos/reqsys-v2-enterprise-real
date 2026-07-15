import unittest

from scripts.build_ux_recovery_remediation_advisory import CARD_ID, build_recommendations, consolidate


class UxRecoveryRemediationAdvisoryTests(unittest.TestCase):
    def test_prioritizes_high_severity_with_traceability(self):
        report = {
            "status": "UX_RECOVERY_REGRESSION_DETECTED",
            "regression_detected": True,
            "alerts": ["recovery_time_increase", "recovery_rate_drop", "confidence_drop"],
            "deltas": {"confidence": -20, "recovery_rate": -8, "recovery_seconds": 7},
            "latest": {"source_run_id": "123", "source_head_sha": "abcdef123", "generated_at": "2026-07-15T18:00:00Z"},
        }
        items = build_recommendations(report)
        self.assertEqual(items[0]["alert"], "recovery_rate_drop")
        self.assertEqual(items[0]["severity"], "high")
        self.assertEqual(items[0]["evidence"]["source_run_id"], "123")

    def test_integrates_alerts_into_existing_card(self):
        dashboard = {"cards": [{"id": "other"}, {"id": CARD_ID, "confidence_percent": 70}]}
        report = {
            "status": "UX_RECOVERY_REGRESSION_DETECTED",
            "regression_detected": True,
            "alerts": ["qualified_sequence_break"],
            "deltas": {"qualified_sequence": -1},
            "latest": {"source_run_id": "456", "source_head_sha": "abcdef456"},
        }
        output = consolidate(dashboard, report)
        card = next(item for item in output["cards"] if item.get("id") == CARD_ID)
        self.assertTrue(card["regression"]["detected"])
        self.assertEqual(card["regression"]["highest_severity"], "medium")
        self.assertFalse(card["regression"]["production_blocker"])
        self.assertEqual(len(output["cards"]), 2)

    def test_stable_report_has_no_recommendations(self):
        dashboard = {"cards": [{"id": CARD_ID}]}
        output = consolidate(dashboard, {"status": "UX_RECOVERY_TREND_STABLE", "alerts": []})
        regression = output["cards"][0]["regression"]
        self.assertFalse(regression["detected"])
        self.assertEqual(regression["recommendations"], [])
        self.assertEqual(regression["highest_severity"], "none")

    def test_requires_readiness_card(self):
        with self.assertRaises(ValueError):
            consolidate({"cards": []}, {"alerts": []})


if __name__ == "__main__":
    unittest.main()
