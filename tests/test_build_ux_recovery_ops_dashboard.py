import unittest

from scripts.build_ux_recovery_ops_dashboard import CARD_ID, build_card, consolidate_dashboard


class UxRecoveryOpsDashboardTests(unittest.TestCase):
    def test_reports_gap_and_traceability_when_pending(self):
        history = [{
            "source_run_id": "123",
            "source_head_sha": "abcdef123456",
            "source_workflow": "recovery-trend",
            "generated_at": "2026-07-15T18:00:00Z",
        }]
        stability = {
            "status": "UX_STABILITY_EVIDENCE_PENDING",
            "standard_gold_ready": False,
            "sample_count": 1,
            "qualified_sample_count": 1,
            "consecutive_qualified_samples": 1,
            "recovery_rate_average": 80,
            "recovery_seconds_average": 22,
            "criteria": {"minimum_samples": 3, "minimum_consecutive_qualified": 2},
        }
        card = build_card(history, stability)
        self.assertEqual(card["latest_evidence"]["source_run_id"], "123")
        self.assertEqual(card["confidence_percent"], 53)
        self.assertIn("coletar mais 2 amostra(s)", card["remaining_gap"])
        self.assertFalse(card["production_blocker"])

    def test_reports_no_technical_gap_when_ready(self):
        stability = {
            "status": "UX_STANDARD_GOLD_EVIDENCE_READY",
            "standard_gold_ready": True,
            "sample_count": 3,
            "qualified_sample_count": 3,
            "consecutive_qualified_samples": 2,
            "recovery_rate_average": 85,
            "recovery_seconds_average": 20,
            "criteria": {"minimum_samples": 3, "minimum_consecutive_qualified": 2},
        }
        card = build_card([], stability)
        self.assertEqual(card["confidence_percent"], 100)
        self.assertEqual(card["remaining_gap"], ["nenhuma lacuna técnica; aguarda aprovação humana"])
        self.assertTrue(card["human_approval_required"])

    def test_dashboard_card_is_idempotent(self):
        card = build_card([], {"sample_count": 0, "consecutive_qualified_samples": 0})
        dashboard = consolidate_dashboard({"cards": [{"id": CARD_ID, "status": "old"}, {"id": "other"}]}, card)
        self.assertEqual(sum(1 for item in dashboard["cards"] if item.get("id") == CARD_ID), 1)
        self.assertEqual(len(dashboard["cards"]), 2)


if __name__ == "__main__":
    unittest.main()
