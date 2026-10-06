from pathlib import Path
import unittest


class FabricHmlNoteriDiscoveryContractTests(unittest.TestCase):
    def test_workflow_is_allowlisted_and_does_not_write_secret(self):
        workflow = Path(".github/workflows/fabric-hml-noteri-discovery.yml").read_text(encoding="utf-8")
        policy = Path(".github/self-hosted-runner-policy.json").read_text(encoding="utf-8")
        script = Path("scripts/fabric_hml_noteri_discovery.py").read_text(encoding="utf-8")

        self.assertIn("runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]", workflow)
        self.assertIn(".github/workflows/fabric-hml-noteri-discovery.yml", policy)
        self.assertIn("FABRIC_CLIENT_SECRET", script)
        self.assertNotIn("gh secret set", script)
        self.assertIn("secret_value_exposed", script)
        self.assertIn("identifiers_exposed", script)
        self.assertIn("fabric_hml_azps_probe.ps1", script)
        helper = Path("scripts/fabric_hml_azps_probe.ps1").read_text(encoding="utf-8")
        self.assertIn("Get-AzAccessToken", helper)
        self.assertNotIn("Write-Host $graphToken", helper)
        self.assertNotIn("Write-Host $fabricToken", helper)

    def test_apply_is_restricted_to_main_dispatch_or_exact_bootstrap_pr(self):
        workflow = Path(".github/workflows/fabric-hml-noteri-discovery.yml").read_text(encoding="utf-8")
        self.assertIn("$authorizedBootstrapPr = (", workflow)
        self.assertIn('"${{ github.event_name }}" -eq "pull_request"', workflow)
        self.assertIn('"${{ github.head_ref }}" -eq "ops/fabric-hml-bootstrap-20260921"', workflow)
        self.assertIn("$authorizedDispatch = (", workflow)
        self.assertIn('"${{ github.event_name }}" -eq "workflow_dispatch"', workflow)
        self.assertIn('"${{ github.ref }}" -eq "refs/heads/main"', workflow)
        self.assertIn("APPLY-FABRIC-HML-NONSECRET-VARS", workflow)

    def test_workflow_provisions_python_with_node24_action(self):
        workflow = Path(".github/workflows/fabric-hml-noteri-discovery.yml").read_text(encoding="utf-8")
        setup = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
        self.assertEqual(workflow.count(setup), 2)
        self.assertIn("python-version: '3.12'", workflow)
        self.assertIn("architecture: 'x64'", workflow)


if __name__ == "__main__":
    unittest.main()
