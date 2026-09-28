"""Contrato do bootstrap do runner Noteri dedicado ao painel-powerbi."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap_painel_powerbi_noteri_runner.py"
WORKFLOW = ROOT / ".github" / "workflows" / "painel-powerbi-noteri-runner-bootstrap.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


class TestPainelPowerBiNoteriRunnerBootstrap(unittest.TestCase):
    def test_alvos_sao_fixos_e_separados_do_reqsys(self) -> None:
        raw = source()
        self.assertIn('TARGET_REPO = "ericson-j-santos/painel-powerbi"', raw)
        self.assertIn('RUNNER_NAME = "Noteri-PainelPowerBI"', raw)
        self.assertIn('"painel-powerbi"', raw)
        self.assertIn('Path(local) / "PainelPowerBI" / "NoteriGitHubRunner"', raw)

    def test_token_eh_efemero_e_nao_logado(self) -> None:
        raw = source()
        self.assertIn("actions/runners/registration-token", raw)
        self.assertIn('"registration_token_persisted": False', raw)
        self.assertIn('"registration_token_logged": False', raw)
        self.assertIn('token = ""', raw)

    def test_processo_filho_nao_herda_tracking_do_job(self) -> None:
        raw = source()
        self.assertIn('env.pop("RUNNER_TRACKING_ID", None)', raw)
        self.assertIn("subprocess.DETACHED_PROCESS", raw)

    def test_sucesso_exige_readback_online_no_github(self) -> None:
        raw = source()
        self.assertIn('str(current.get("status") or "") == "online"', raw)
        self.assertIn("labels_ok(current)", raw)
        self.assertIn('"state": "runner_online"', raw)

    def test_workflow_eh_restrito_a_branch_operacional_e_noteri(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "ops/painel-powerbi-noteri-runner-bootstrap-20260928",
            raw,
        )
        self.assertIn(
            "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]",
            raw,
        )
        self.assertNotIn("pull_request:", raw)
        self.assertIn("REGISTER-PAINEL-POWERBI-NOTERI-RUNNER", raw)

    def test_workflow_esta_na_allowlist_self_hosted(self) -> None:
        raw = POLICY.read_text(encoding="utf-8")
        self.assertIn(
            ".github/workflows/painel-powerbi-noteri-runner-bootstrap.yml",
            raw,
        )


if __name__ == "__main__":
    unittest.main()
