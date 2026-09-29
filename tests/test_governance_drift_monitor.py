from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "governance_drift_monitor.py"
SPEC = importlib.util.spec_from_file_location("governance_drift_monitor", SCRIPT)
assert SPEC and SPEC.loader
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)

SHA = "a" * 40


def compliant_repository() -> dict:
    return {
        "full_name": "ericson-j-santos/reqsys-v2-enterprise-real",
        "allow_auto_merge": True,
    }


def compliant_rulesets() -> list[dict]:
    return [
        {
            "id": 17998541,
            "target": "branch",
            "enforcement": "active",
            "conditions": {
                "ref_name": {
                    "include": ["~DEFAULT_BRANCH"],
                    "exclude": [],
                }
            },
            "bypass_actors": [],
            "rules": [
                {"type": "deletion"},
                {"type": "non_fast_forward"},
                {"type": "pull_request"},
            ],
        }
    ]


def write_baseline(root: Path) -> None:
    files = {
        ".github/workflows/ci.yml": "name: CI — ReqSys v2 Enterprise\n",
        ".github/workflows/governance-quality-gates.yml": "name: Governance Quality Gates\n",
        ".github/workflows/branch-protection-audit.yml": "name: Branch Protection Audit\n",
        ".github/workflows/pr-evidence-gate.yml": "name: PR Evidence Gate\n",
        ".github/workflows/governed-pr-automation.yml": """
name: Governed PR Automation
jobs:
  merge:
    steps:
      - uses: actions/github-script@deadbeef
        with:
          script: |
            const triggerHeadSha = context.payload.workflow_run.head_sha;
            if (pr.head.sha !== triggerHeadSha) return;
            const current = await github.rest.pulls.get({});
            if (current.head.sha !== triggerHeadSha) return;
            await github.rest.pulls.merge({
              sha: triggerHeadSha,
            });
""",
    }
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class GovernanceDriftMonitorTests(unittest.TestCase):
    def analyze(self, root: Path, repo: dict | None = None, rulesets=None):
        return monitor.analyze(
            repo or compliant_repository(),
            compliant_rulesets() if rulesets is None else rulesets,
            root=root,
            source_sha=SHA,
            generated_at="2026-09-29T22:00:00+00:00",
        )

    def test_compliant_baseline_has_no_material_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_baseline(root)
            report = self.analyze(root)

        self.assertFalse(report["material_drift"])
        self.assertEqual(report["active_drifts"], [])
        self.assertEqual(
            report["mappings"]["Settings Hardening Evidence"]["workflow"],
            "Branch Protection Audit",
        )

    def test_each_required_control_removal_is_material(self):
        for kind, (relative, _) in monitor.CONTROL_FILES.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_baseline(root)
                (root / relative).unlink()
                report = self.analyze(root)
                self.assertIn(kind, report["active_drifts"])

    def test_bypass_actor_flags_admin_protection_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_baseline(root)
            rulesets = compliant_rulesets()
            rulesets[0]["bypass_actors"] = [{"actor_type": "OrganizationAdmin", "bypass_mode": "always"}]
            report = self.analyze(root, rulesets=rulesets)

        self.assertIn("admin_protection_altered", report["active_drifts"])

    def test_missing_non_fast_forward_flags_force_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_baseline(root)
            rulesets = compliant_rulesets()
            rulesets[0]["rules"] = [
                rule for rule in rulesets[0]["rules"] if rule["type"] != "non_fast_forward"
            ]
            report = self.analyze(root, rulesets=rulesets)

        self.assertIn("force_push_enabled", report["active_drifts"])

    def test_missing_deletion_rule_flags_branch_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_baseline(root)
            rulesets = compliant_rulesets()
            rulesets[0]["rules"] = [
                rule for rule in rulesets[0]["rules"] if rule["type"] != "deletion"
            ]
            report = self.analyze(root, rulesets=rulesets)

        self.assertIn("deletion_enabled", report["active_drifts"])

    def test_auto_merge_disabled_is_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_baseline(root)
            repo = compliant_repository()
            repo["allow_auto_merge"] = False
            report = self.analyze(root, repo=repo)

        self.assertIn("auto_merge_disabled", report["active_drifts"])

    def test_expected_head_sha_contract_requires_pre_merge_read_and_sha_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_baseline(root)
            workflow = root / ".github/workflows/governed-pr-automation.yml"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "              sha: triggerHeadSha,\n",
                    "              merge_method: 'squash',\n",
                ),
                encoding="utf-8",
            )
            report = self.analyze(root)

        self.assertIn("expected_head_sha_weakened", report["active_drifts"])
        evidence = report["controls"]["expected_head_sha"]["required_markers"]
        self.assertFalse(evidence["merge_uses_expected_sha"])

    def test_report_contains_evidence_impact_risk_and_safe_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_baseline(root)
            (root / ".github/workflows/pr-evidence-gate.yml").unlink()
            report = self.analyze(root)
            markdown = monitor.render_markdown(report)

        self.assertIn("Evidência atual", markdown)
        self.assertIn("Impacto", markdown)
        self.assertIn("Risco", markdown)
        self.assertIn("Menor correção segura e idempotente", markdown)
        self.assertIn(monitor.MARKER, markdown)


if __name__ == "__main__":
    unittest.main()
