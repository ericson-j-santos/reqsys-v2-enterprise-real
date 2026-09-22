import unittest
from datetime import datetime, timezone

from scripts.build_ux_remediation_governance_metrics import build_metrics, consolidate


class UxRemediationGovernanceMetricsTests(unittest.TestCase):
    def test_calculates_sla_closure_reopen_and_mttr(self):
        history = [
            {"id":"1:a","state":"resolved","severity":"high","recommended_due_at":"2026-07-15T12:00:00Z","resolved_at":"2026-07-15T11:00:00Z","recovery_hours":5,"resolution_signature":"sig","qualified_resolution_run_id":"2"},
            {"id":"2:b","state":"open","severity":"medium","recommended_due_at":"2026-07-15T10:00:00Z"},
        ]
        audits = [{"from_state":"resolved","to_state":"in_progress"}]
        metrics = build_metrics(history, audits, now=datetime(2026,7,15,13,tzinfo=timezone.utc))
        self.assertEqual(metrics["within_sla_percent"], 50.0)
        self.assertEqual(metrics["validated_closure_rate_percent"], 100.0)
        self.assertEqual(metrics["reopening_count"], 1)
        self.assertEqual(metrics["mttr_hours_by_severity"]["high"], 5.0)
        self.assertEqual(metrics["overdue_open_count"], 1)
        self.assertFalse(metrics["production_blocker"])

    def test_integrates_metrics_into_dashboard(self):
        dashboard = {"cards":[{"id":"other"},{"id":"ux-recovery-standard-gold-readiness"}]}
        output = consolidate(dashboard, {"status":"ok"})
        card = next(item for item in output["cards"] if item["id"] == "ux-recovery-standard-gold-readiness")
        self.assertEqual(card["remediation_governance"]["status"], "ok")
        self.assertEqual(len(output["cards"]), 2)

    def test_requires_readiness_card(self):
        with self.assertRaises(ValueError):
            consolidate({"cards":[]}, {})


if __name__ == "__main__":
    unittest.main()
