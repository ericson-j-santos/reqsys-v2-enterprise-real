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

from scripts import teams_notification_slo_metrics as slo_metrics

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
    def run_entry(run_id: int, event: str, conclusion: str) -> dict:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "id": run_id,
            "created_at": now,
            "run_started_at": now,
            "updated_at": now,
            "status": "completed",
            "event": event,
            "conclusion": conclusion,
            "head_sha": "a" * 40,
        }

    def execute(self, records: list[dict]) -> dict:
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
                    exec(compile(self.source, str(WORKFLOW), "exec"), {"__name__": "__main__"})
            finally:
                os.chdir(previous)
            result = json.loads((root / "teams-slo-evidence/teams-notification-slo.json").read_text(encoding="utf-8"))
            outputs = dict(
                line.split("=", 1)
                for line in (root / "output").read_text(encoding="utf-8").splitlines()
            )
            self.assertEqual(outputs["state"], result["state"])
            self.assertEqual(outputs["workflow_state"], result["workflow_execution_state"])
            self.assertEqual(outputs["delivery_state"], "unverified")
            self.assertEqual(outputs["delivery_verified"], "false")
            markdown = (root / "teams-slo-evidence/teams-notification-slo.md").read_text(encoding="utf-8")
            self.assertEqual((root / "summary").read_text(encoding="utf-8"), markdown)
            self.assertIn("entrega NÃO verificada", markdown)
            return result

    def sample(self) -> list[dict]:
        return [
            self.run_entry(1, "schedule", "failure"),
            self.run_entry(2, "schedule", "success"),
            self.run_entry(3, "workflow_dispatch", "success"),
            self.run_entry(4, "push", "success"),
            self.run_entry(5, "workflow_run", "success"),
            self.run_entry(6, "workflow_run", "failure"),
            self.run_entry(7, "workflow_run", "cancelled"),
        ]

    def test_excludes_watchdog_and_manual_diagnostics(self):
        report = self.execute(self.sample())
        self.assertEqual(report["schema_version"], "2.0.0")
        self.assertEqual(report["total_runs"], 4)
        self.assertEqual(report["successful_runs"], 2)
        self.assertEqual(report["failed_runs"], 2)
        self.assertEqual(report["excluded_non_candidate_runs"], 3)
        self.assertEqual(report["all_events"]["schedule"], 2)
        self.assertEqual(report["workflow_conclusions"]["cancelled"], 1)
        self.assertEqual(report["workflow_conclusions"]["failure"], 1)
        self.assertEqual(report["workflow_execution_errors"], 1)
        self.assertEqual(report["workflow_execution_state"], "breached")
        self.assertEqual(report["delivery_candidate_events"], ["push", "workflow_run"])
        self.assertEqual(report["locator_watch"]["total_runs"], 2)
        self.assertEqual(report["locator_watch"]["non_successful_runs"], 1)

    def test_execution_success_is_never_delivery_proof(self):
        report = self.execute([self.run_entry(1, "workflow_run", "success")])
        self.assertEqual(report["success_rate_percent"], 100.0)
        self.assertEqual(report["workflow_execution_state"], "healthy")
        self.assertEqual(report["state"], "unverified_delivery")
        self.assertEqual(report["delivery_state"], "unverified")
        self.assertIs(report["delivery_verified"], False)
        self.assertIsNone(report["delivery_success_rate_percent"])
        self.assertIsNone(report["remaining_delivery_error_budget"])
        self.assertNotRegex(self.workflow, r"gh\s+issue\s+close")
        self.assertIn("if: steps.slo.outputs.delivery_verified != 'true'", self.workflow)

    def test_zero_candidate_data_is_not_healthy(self):
        report = self.execute([self.run_entry(1, "schedule", "success")])
        self.assertEqual(report["total_runs"], 0)
        self.assertEqual(report["workflow_execution_state"], "insufficient_data")
        self.assertEqual(report["state"], "insufficient_data")
        self.assertEqual(report["delivery_state"], "unverified")
        self.assertIs(report["delivery_verified"], False)

    def test_replay_and_negative_control_detect_previous_filtering_defect(self):
        sample = self.sample()
        first = self.execute(sample)
        second = self.execute(sample)
        stable_keys = (
            "total_runs", "successful_runs", "failed_runs", "all_events",
            "workflow_conclusions", "locator_watch", "state",
        )
        for key in stable_keys:
            self.assertEqual(first[key], second[key])
        legacy_events = frozenset({"push", "workflow_run", "schedule", "workflow_dispatch"})
        with patch.object(slo_metrics, "CANDIDATE_EVENTS", legacy_events):
            legacy = self.execute(sample)
        self.assertEqual(legacy["total_runs"], 7)
        with self.assertRaises(AssertionError):
            self.assertEqual(legacy["total_runs"], 4)
        restored = self.execute(sample)
        for key in stable_keys:
            self.assertEqual(first[key], restored[key])


if __name__ == "__main__":
    unittest.main()
