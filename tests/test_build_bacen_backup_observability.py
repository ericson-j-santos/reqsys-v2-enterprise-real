from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_bacen_backup_observability import (
    Outputs,
    build_card,
    build_dashboard,
    build_markdown,
    evaluate,
    write_outputs,
)


class BackupObservabilityTests(unittest.TestCase):
    def healthy_evidence(self) -> dict[str, object]:
        return {
            "control_id": "BACEN-04",
            "result": "passed",
            "integrity_match": True,
            "production_touched": False,
            "rpo_minutes": 0,
            "rpo_target_minutes": 1440,
            "rto_seconds": 0.159,
            "rto_target_seconds": 14400,
            "source_snapshot": {"row_count": 1000},
            "target_snapshot": {"row_count": 1000},
            "backup_sha256": "a" * 64,
            "correlation_id": "corr-1",
        }

    def test_healthy_evidence_is_healthy(self) -> None:
        health, reasons = evaluate(self.healthy_evidence(), "success")
        self.assertEqual(health, "healthy")
        self.assertEqual(len(reasons), 1)

    def test_missing_evidence_is_critical(self) -> None:
        health, reasons = evaluate(None, "failure")
        self.assertEqual(health, "critical")
        self.assertIn("evidência ausente", reasons)

    def test_threshold_violation_is_critical(self) -> None:
        evidence = self.healthy_evidence()
        evidence["rto_seconds"] = 20000
        health, reasons = evaluate(evidence, "success")
        self.assertEqual(health, "critical")
        self.assertTrue(any("RTO excedido" in reason for reason in reasons))

    def test_outputs_are_generated(self) -> None:
        dashboard = build_dashboard(
            self.healthy_evidence(),
            evidence_error=None,
            workflow_status="success",
            repository="owner/repo",
            sha="abcdef123456",
            run_url="https://example.test/run/1",
            generated_at="2026-08-01T16:00:00+00:00",
            next_scheduled_at="2026-10-01T09:17:00Z",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outputs = Outputs(root / "x.json", root / "x.md", root / "x.html", root / "card.json")
            write_outputs(outputs, dashboard)
            self.assertEqual(json.loads(outputs.json_path.read_text())["health"], "healthy")
            self.assertIn("Dashboard BACEN-04", build_markdown(dashboard))
            self.assertEqual(build_card(dashboard)["version"], "1.2")
            for path in outputs.__dict__.values():
                self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
