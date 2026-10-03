import unittest
from datetime import datetime, timezone

from scripts.build_ux_remediation_lifecycle import build_lifecycle


class UxRemediationLifecycleTests(unittest.TestCase):
    def test_builds_sla_owner_and_due_date(self):
        dashboard = {"cards": [{
            "id": "ux-recovery-standard-gold-readiness",
            "latest_evidence": {"source_run_id": "123"},
            "regression": {"recommendations": [{
                "alert": "recovery_rate_drop",
                "severity": "high",
                "evidence": {"generated_at": "2026-07-15T10:00:00Z", "source_head_sha": "abcdef123"},
            }]},
        }]}
        output, history = build_lifecycle(dashboard, [], now=datetime(2026, 7, 15, 12, tzinfo=timezone.utc))
        lifecycle = output["cards"][0]["remediation_lifecycle"]
        self.assertEqual(lifecycle["open_count"], 1)
        self.assertEqual(lifecycle["items"][0]["sla_hours"], 24)
        self.assertEqual(lifecycle["items"][0]["suggested_owner"], "UX_UI")
        self.assertEqual(len(history), 1)
        self.assertFalse(lifecycle["production_blocker"])

    def test_clear_when_no_recommendations(self):
        dashboard = {"cards": [{"id": "ux-recovery-standard-gold-readiness", "regression": {"recommendations": []}}]}
        output, _ = build_lifecycle(dashboard, [])
        self.assertEqual(output["cards"][0]["remediation_lifecycle"]["status"], "UX_REMEDIATION_CLEAR")

    def test_preserves_resolved_history_and_mttr(self):
        dashboard = {"cards": [{"id": "ux-recovery-standard-gold-readiness", "regression": {"recommendations": []}}]}
        previous = [{"id": "1:a", "state": "resolved", "recovery_hours": 4}, {"id": "2:b", "state": "resolved", "recovery_hours": 8}]
        output, _ = build_lifecycle(dashboard, previous)
        self.assertEqual(output["cards"][0]["remediation_lifecycle"]["mean_time_to_recovery_hours"], 6.0)

    def test_requires_readiness_card(self):
        with self.assertRaises(ValueError):
            build_lifecycle({"cards": []}, [])


if __name__ == "__main__":
    unittest.main()
