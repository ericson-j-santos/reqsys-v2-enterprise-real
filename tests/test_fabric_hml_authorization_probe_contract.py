"""Contrato do probe temporário de autorização Fabric HML.

O probe é descartável e roda em runner self-hosted com sessão Azure CLI do
operador. Os testes abaixo travam o que o torna seguro: escopo restrito à
branch efêmera, execução exclusivamente read-only, SHA imutável no checkout e
evidência sanitizada. Travam também a separação de arquivos: o probe não pode
voltar a sobrescrever o workflow canônico de discovery.
"""

from __future__ import annotations

import unittest
from pathlib import Path

PROBE_WORKFLOW = Path(".github/workflows/fabric-hml-authorization-probe.yml")
DISCOVERY_WORKFLOW = Path(".github/workflows/fabric-hml-noteri-discovery.yml")
PROBE_SCRIPT = Path("scripts/fabric_hml_authorization_probe_temp.py")
PROBE_BRANCH = "probe/fabric-hml-authorization-20260921"


class FabricHmlAuthorizationProbeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = PROBE_WORKFLOW.read_text(encoding="utf-8")
        self.script = PROBE_SCRIPT.read_text(encoding="utf-8")

    def test_probe_has_its_own_workflow_file(self) -> None:
        self.assertTrue(PROBE_WORKFLOW.is_file())
        self.assertIn("name: Fabric HML Authorization Probe", self.workflow)

    def test_probe_is_allowlisted_for_self_hosted_runners(self) -> None:
        policy = Path(".github/self-hosted-runner-policy.json").read_text(encoding="utf-8")
        self.assertIn(
            "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]", self.workflow
        )
        self.assertIn(".github/workflows/fabric-hml-authorization-probe.yml", policy)

    def test_probe_does_not_replace_the_discovery_workflow(self) -> None:
        discovery = DISCOVERY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("name: Fabric HML Noteri Discovery", discovery)
        self.assertNotIn("fabric_hml_authorization_probe_temp", discovery)

    def test_probe_runs_only_on_the_ephemeral_branch(self) -> None:
        self.assertIn(f"github.head_ref == '{PROBE_BRANCH}'", self.workflow)

    def test_probe_checks_out_the_immutable_head_sha(self) -> None:
        self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", self.workflow)

    def test_probe_has_read_only_permissions(self) -> None:
        self.assertIn("permissions:\n  contents: read\n", self.workflow)

    def test_probe_publishes_sanitized_evidence(self) -> None:
        self.assertIn(
            "path: artifacts/fabric-hml-authorization-probe/evidence.json",
            self.workflow,
        )
        self.assertIn("if-no-files-found: error", self.workflow)
        self.assertIn('"secret_value_exposed": False', self.script)
        self.assertIn('"identifiers_exposed": False', self.script)

    def test_probe_script_performs_no_write_operations(self) -> None:
        for forbidden in (
            "roleAssignments\", data=",
            '"create"',
            '"delete"',
            "method=\"POST\"",
            "method=\"PUT\"",
            "method=\"PATCH\"",
            "method=\"DELETE\"",
        ):
            self.assertNotIn(forbidden, self.script)
        self.assertNotIn("--apply", self.script)


if __name__ == "__main__":
    unittest.main()
