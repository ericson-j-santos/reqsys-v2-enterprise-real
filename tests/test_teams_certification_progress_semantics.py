"""Testa o proprio codigo de calculo da Issue #1358 sem rede nem envio Teams."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/teams-certification-progress-status.yml"


def item(identifier: int, event: str, conclusion: str, days: int = 1) -> dict:
    created = datetime.now(timezone.utc) - timedelta(days=days)
    return {"id": identifier, "event": event, "conclusion": conclusion,
            "status": "completed", "created_at": created.isoformat()}


class CertificationSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        marker = "          python - <<'PY'\n"
        start = cls.workflow.index(marker) + len(marker)
        end = cls.workflow.index("\n          PY", start)
        cls.source = textwrap.dedent(cls.workflow[start:end])
        compile(cls.source, str(WORKFLOW), "exec")

    def execute(self, deliveries: list[dict], monitors: list[dict]) -> tuple[dict, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "GITHUB_REPOSITORY": "owner/reqsys", "GITHUB_OUTPUT": str(root / "output"),
                "GITHUB_SERVER_URL": "https://github.com", "GITHUB_RUN_ID": "41984951174",
                "DELIVERY_WORKFLOW": "teams-commit-notification.yml",
                "MONITOR_WORKFLOW": "teams-dashboard-availability-monitor.yml",
                "MIN_DELIVERY_RUNS": "20", "MIN_MONITOR_RUNS": "20",
                "PROVISIONAL_DAYS": "7", "DEFINITIVE_DAYS": "30", "TARGET_PERCENT": "99.0",
            }

            def mock_gh(args, **kwargs):
                records = deliveries if "teams-commit-notification.yml" in args[-1] else monitors
                return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps([{"workflow_runs": records}]))

            old_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, env), patch.object(subprocess, "run", side_effect=mock_gh):
                    exec(compile(self.source, str(WORKFLOW), "exec"), {"__name__": "__main__"})
                report = json.loads((root / "teams-certification-progress/progress.json").read_text(encoding="utf-8"))
                markdown = (root / "teams-certification-progress/status.md").read_text(encoding="utf-8")
            finally:
                os.chdir(old_cwd)
        return report, markdown

    def healthy_sample(self):
        delivery = [item(i, "push" if i % 2 else "workflow_run", "success") for i in range(1, 21)]
        monitor = [item(i + 100, "schedule", "success") for i in range(1, 21)]
        delivery.append(item(91, "push", "success", days=40))
        monitor.append(item(191, "schedule", "success", days=40))
        return delivery, monitor

    def test_workflows_verdes_nao_autorizam_certificacao_sem_readback(self):
        deliveries, monitors = self.healthy_sample()
        report, md = self.execute(deliveries, monitors)
        self.assertEqual(report["schema_version"], "2.0.0")
        self.assertEqual(report["state"], "quality_blocked")
        self.assertEqual(report["target_percent"], 99.0)
        self.assertEqual(report["delivery_state"], "unverified")
        self.assertFalse(report["delivery_verified"])
        self.assertIsNone(report["delivery_success_rate_percent"])
        self.assertEqual(report["rolling_7d"]["delivery"]["success_rate_percent"], 100.0)
        self.assertEqual(report["rolling_7d"]["availability_monitor"]["success_rate_percent"], 100.0)
        self.assertIn("proxy, não entrega", md)
        self.assertIn("recibo independente", md)
        self.assertTrue(md.startswith("<!-- reqsys-operational-panel -->"))

    def test_watchdog_e_execucao_manual_nao_contam_como_entrega(self):
        deliveries, monitors = self.healthy_sample()
        deliveries += [item(50, "schedule", "failure"), item(51, "workflow_dispatch", "failure")]
        report, _ = self.execute(deliveries, monitors)
        self.assertEqual(report["rolling_7d"]["delivery"]["total"], 20)
        self.assertEqual(report["rolling_7d"]["delivery"]["failures"], 0)
        self.assertEqual(report["state"], "quality_blocked")

    def test_falhas_reais_de_workflow_e_monitor_nao_sao_ocultadas(self):
        deliveries, monitors = self.healthy_sample()
        deliveries.append(item(52, "workflow_run", "failure"))
        monitors.append(item(152, "schedule", "failure"))
        first, _ = self.execute(deliveries, monitors)
        second, _ = self.execute(deliveries, monitors)
        self.assertEqual(first["rolling_7d"], second["rolling_7d"])
        self.assertEqual(first["rolling_7d"]["delivery"]["failures"], 1)
        self.assertEqual(first["rolling_7d"]["availability_monitor"]["failures"], 1)
        self.assertLess(first["rolling_7d"]["delivery"]["success_rate_percent"], 99)
        self.assertLess(first["rolling_7d"]["availability_monitor"]["success_rate_percent"], 99)
        self.assertEqual(first["state"], "quality_blocked")

    def test_gates_e_esquema_preservados(self):
        self.assertIn('frozenset({"push", "workflow_run"})', self.workflow)
        self.assertIn("delivery_verified\n              and delivery_7d", self.workflow)
        self.assertIn("delivery_verified\n              and delivery_30d", self.workflow)
        self.assertIn('"metric_kind": "workflow_execution_proxy_not_delivery"', self.workflow)


if __name__ == "__main__":
    unittest.main()
