import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/branch-protection-audit.yml"
CONFIG = ROOT / "scripts/configure_report_builder_main_protection_risk3.py"
RUNNER = ROOT / "scripts/run_report_builder_main_protection_local.py"

EXPECTED_HEAD = "c4e5b4ffd677f854ca1107330c87312d995c619e"


class ReportBuilderProtectionContractTests(unittest.TestCase):
    def test_risk3_action_is_fixed_and_contains_no_secret_argument(self) -> None:
        raw = CONFIG.read_text(encoding="utf-8")
        self.assertIn('ACTION_ID = "reqsys.report-builder-main-protection.dev"', raw)
        self.assertIn(
            'SCOPE = "repo://ericson-j-santos/report-builder-platform/branch/main"',
            raw,
        )
        self.assertIn('"scripts/run_report_builder_main_protection_local.py"', raw)
        self.assertNotIn("--token", raw)
        self.assertNotIn("--secret", raw)

    def test_local_executor_is_fail_closed_and_bound_to_evidence_sha(self) -> None:
        raw = RUNNER.read_text(encoding="utf-8")
        self.assertIn(
            'TARGET_REPOSITORY = "ericson-j-santos/report-builder-platform"',
            raw,
        )
        self.assertIn('TARGET_BRANCH = "main"', raw)
        self.assertIn("EVIDENCE_PR_NUMBER = 5", raw)
        self.assertIn(f'EXPECTED_EVIDENCE_SHA = "{EXPECTED_HEAD}"', raw)
        self.assertIn('"Quality / Python 3.11"', raw)
        self.assertIn('"Quality / Python 3.14"', raw)
        self.assertIn('env.pop("GH_TOKEN", None)', raw)
        self.assertIn('env.pop("GITHUB_TOKEN", None)', raw)
        self.assertIn('"required_checks_not_green"', raw)
        self.assertIn('"evidence_pr_head_changed_before_write"', raw)
        self.assertIn('"target_sha_changed_before_write"', raw)
        self.assertIn('"target_sha_changed_after_write"', raw)
        self.assertIn('"branch_protection_update_failed"', raw)
        self.assertIn('"PROTECTION_APPLIED"', raw)
        self.assertIn('"ALREADY_COMPLIANT"', raw)
        self.assertIn('"secret_value_exposed": False', raw)

    def test_workflow_uses_session_launcher_and_exact_risk3(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ops/report-builder-main-protection-20260923", raw)
        self.assertIn(
            "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]",
            raw,
        )
        self.assertIn("session_launcher.py", raw)
        self.assertIn("SESSION_LAUNCH_OK", raw)
        self.assertIn('"origin/${{ github.ref_name }}"', raw)
        self.assertIn("owner_risk3_gateway.py", raw)
        self.assertIn("reqsys.report-builder-main-protection.dev", raw)
        self.assertIn(
            "repo://ericson-j-santos/report-builder-platform/branch/main",
            raw,
        )
        self.assertIn("ENABLE-REPORT-BUILDER-MAIN-PROTECTION-ONCE", raw)
        self.assertIn("DISABLE-REPORT-BUILDER-MAIN-PROTECTION-ONCE", raw)
        self.assertIn("Remover autorização Risk3 temporária Report Builder", raw)
        self.assertNotIn("GITHUB_PAT", raw)


if __name__ == "__main__":
    unittest.main()
