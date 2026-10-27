"""Regressão do produtor real do SLO; não envia mensagens nem acessa rede."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/teams-notification-slo.yml"


class TeamsSloSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        start = cls.workflow.index("          python - <<'PY'\n") + len("          python - <<'PY'\n")
        end = cls.workflow.index("\n          PY", start)
        cls.source = textwrap.dedent(cls.workflow[start:end])

    @staticmethod
    def run_entry(event: str, conclusion: str) -> dict:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "id": len(event) * 10 + len(conclusion),
            "created_at": now,
            "run_started_at": now,
            "updated_at": now,
            "status": "completed",
            "event": event,
            "conclusion": conclusion,
            "head_sha": "a" * 40,
        }

    def execute(self, records: list[dict], source: str | None = None) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {
                "GITHUB_REPOSITORY": "owner/reqsys",
                "WORKFLOW_FILE": "teams-commit-notification.yml",
                "WINDOW_DAYS": "30",
                "SLO_TARGET": "99.0",
                "GITHUB_OUTPUT": str(root / "output"),
                "GITHUB_STEP_SUMMARY": str(root / "summary"),
            }
            fake = SimpleNamespace(
                returncode=0,
                stdout=json.dumps([{"workflow_runs": records}]),
                stderr="",
            )
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, env), patch.object(subprocess, "run", return_value=fake):
                    exec(compile(source or self.source, str(WORKFLOW), "exec"), {"__name__": "__main__"})
            finally:
                os.chdir(previous)
            result = json.loads((root / "teams-slo-evidence/teams-notification-slo.json").read_text(encoding="utf-8"))
            outputs = (root / "output").read_text(encoding="utf-8")
            self.assertIn("delivery_verified=false", outputs)
            self.assertIn("state=unverified_delivery", outputs)
            return result

    def sample(self) -> list[dict]:
        return [
            self.run_entry("schedule", "failure"),
            self.run_entry("schedule", "success"),
            self.run_entry("workflow_dispatch", "success"),
            self.run_entry("push", "success"),
            self.run_entry("workflow_run", "success"),
            self.run_entry("workflow_run", "failure"),
            self.run_entry("workflow_run", "cancelled"),
        ]

    def test_excludes_watchdog_and_manual_diagnostics(self):
        report = self.execute(self.sample())
        self.assertEqual(report["total_runs"], 4)
        self.assertEqual(report["successful_runs"], 2)
        self.assertEqual(report["failed_runs"], 2)
        self.assertEqual(report["excluded_non_notification_runs"], 3)
        self.assertEqual(report["event_breakdown"]["schedule"], 2)
        self.assertEqual(report["conclusion_breakdown"]["cancelled"], 1)
        self.assertEqual(report["actual_failure_conclusions"], 1)
        self.assertEqual(report["execution_state"], "breached")
        self.assertEqual(report["notification_event_filter"], ["push", "workflow_run"])

    def test_execution_success_is_never_delivery_proof(self):
        report = self.execute([self.run_entry("workflow_run", "success")])
        self.assertEqual(report["success_rate_percent"], 100.0)
        self.assertEqual(report["execution_state"], "healthy")
        self.assertEqual(report["state"], "unverified_delivery")
        self.assertEqual(report["delivery_slo_state"], "unverified")
        self.assertIs(report["delivery_verified"], False)
        self.assertIsNone(report["delivery_success_rate_percent"])
        self.assertIsNone(report["delivery_error_budget"])
        self.assertIn("steps.slo.outputs.delivery_verified == 'true'", self.workflow)

    def test_zero_candidate_data_is_not_healthy(self):
        report = self.execute([self.run_entry("schedule", "success")])
        self.assertEqual(report["total_runs"], 0)
        self.assertEqual(report["execution_state"], "insufficient_data")
        self.assertEqual(report["state"], "unverified_delivery")

    def test_replay_and_negative_control_detect_previous_filtering_defect(self):
        sample = self.sample()
        first = self.execute(sample)
        second = self.execute(sample)
        for key in ("total_runs", "successful_runs", "failed_runs", "event_breakdown", "conclusion_breakdown", "state"):
            self.assertEqual(first[key], second[key])
        original = 'runs = [run for run in all_completed_runs if run.get("event") in notification_events]'
        self.assertIn(original, self.source)
        legacy = self.source.replace(original, 'runs = all_completed_runs')
        with self.assertRaises(AssertionError):
            self.assertEqual(self.execute(sample, legacy)["total_runs"], 4)


if __name__ == "__main__":
    unittest.main()
