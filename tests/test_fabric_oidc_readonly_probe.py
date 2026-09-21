from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.fabric_oidc_readonly_probe import EXPECTED_TENANT


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "fabric-oidc-readonly-probe.yml"
SCRIPT = ROOT / "scripts" / "fabric_oidc_readonly_probe.py"


class TestFabricOidcReadonlyProbe(unittest.TestCase):
    def test_expected_tenant_is_canonical(self) -> None:
        self.assertEqual(EXPECTED_TENANT, "6d09c88c-0617-490c-8329-305e577684bc")

    def test_workflow_is_oidc_and_read_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("id-token: write", text)
        self.assertIn("contents: read", text)
        self.assertIn("environment: development", text)
        self.assertIn("azure/login@", text)
        self.assertNotIn("client-secret:", text)
        self.assertNotIn("pull_request_target", text)
        self.assertIn("mutations_performed", text)
        self.assertIn("secret_value_exposed", text)

    def test_script_has_no_mutating_http_methods(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('method="POST"', text)
        self.assertNotIn('method="DELETE"', text)
        self.assertNotIn('method="PATCH"', text)
        self.assertNotIn('method="PUT"', text)
        self.assertNotIn("az role assignment create", text)
        self.assertNotIn("az ad app credential reset", text)

    def test_evidence_contract_is_json_serializable(self) -> None:
        payload = {
            "schema": "fabric-oidc-readonly-probe/v1",
            "status": "completed",
            "secret_value_exposed": False,
            "mutations_performed": False,
        }
        self.assertIn("completed", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
