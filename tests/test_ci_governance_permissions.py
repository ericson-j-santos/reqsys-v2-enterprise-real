"""Regressoes do escopo de permissoes GitHub Actions do ReqSys."""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts.ci_governance_permissions import audit_permissions

ROOT = Path(__file__).resolve().parents[1]
CRITICAL = (
    "ci.yml",
    "pr-evidence-gate.yml",
    "pr-governed-ci-validation.yml",
    "pr-ci-watch.yml",
    "pr-conflict-guard.yml",
    "ci-runtime-health-summary.yml",
)
WATCH = ".github/workflows/pr-ci-watch.yml"
CONFLICT = ".github/workflows/pr-conflict-guard.yml"


class TestCIGovernanceScopedPermissions(unittest.TestCase):
    @staticmethod
    def watch_content() -> str:
        return (ROOT / WATCH).read_text(encoding="utf-8")

    def test_critical_workflows_real_permissions_pass_with_scoped_policy(self):
        for name in CRITICAL:
            with self.subTest(name=name):
                path = f".github/workflows/{name}"
                content = (ROOT / path).read_text(encoding="utf-8")
                report = audit_permissions(content, path)
                self.assertEqual(report["violations"], [], report)

    def test_existing_job_permissions_are_visible_and_audited(self):
        report = audit_permissions(self.watch_content(), WATCH)
        self.assertEqual(report["violations"], [])
        self.assertIn("structural-queue:contents: write", report["observed"])
        self.assertIn("structural-queue:pull-requests: write", report["observed"])
        self.assertIn("remediate-workflow-run:actions: write", report["observed"])
        self.assertNotIn("workflow:contents: write", report["observed"])

    def test_global_elevation_fails_even_if_same_job_is_allowlisted(self):
        modified = self.watch_content().replace(
            "permissions: {}",
            "permissions:\n  contents: write",
            1,
        )
        report = audit_permissions(modified, WATCH)
        self.assertIn(
            "workflow:contents: unexpected_elevated_permission",
            report["violations"],
        )

    def test_other_job_does_not_inherit_structural_queue_allowlist(self):
        modified = self.watch_content().replace(
            "  watch-pr:\n",
            "  watch-pr:\n    permissions:\n      contents: write\n",
            1,
        )
        report = audit_permissions(modified, WATCH)
        self.assertIn(
            "watch-pr:contents: unexpected_elevated_permission",
            report["violations"],
        )

    def test_unlisted_scope_and_write_all_are_rejected(self):
        modified = self.watch_content().replace(
            "      actions: write",
            "      administration: write",
            1,
        )
        self.assertTrue(
            any(
                "remediate-workflow-run:administration" in issue
                for issue in audit_permissions(modified, WATCH)["violations"]
            )
        )
        for source in (
            self.watch_content().replace("permissions: {}", "permissions: write-all", 1),
            self.watch_content().replace(
                "      actions: write", "    permissions: write-all", 1
            ),
        ):
            with self.subTest(kind=source.count("write-all")):
                self.assertTrue(audit_permissions(source, WATCH)["violations"])

    def test_comment_and_script_strings_do_not_count_as_permissions(self):
        content = self.watch_content() + (
            "\n# contents: write\n# pull-requests: write\n"
        )
        self.assertEqual(audit_permissions(content, WATCH)["violations"], [])

    def test_invalid_yaml_and_missing_top_level_policy_fail_closed(self):
        self.assertIn(
            "workflow_yaml_invalid",
            audit_permissions("jobs: [\n", WATCH)["violations"],
        )
        content = self.watch_content().replace("permissions: {}", "# permissions omitted", 1)
        self.assertIn(
            "workflow_permissions_missing",
            audit_permissions(content, WATCH)["violations"],
        )

    def test_conflict_guard_known_issues_write_is_not_broadly_allowed(self):
        content = (ROOT / CONFLICT).read_text(encoding="utf-8")
        self.assertEqual(audit_permissions(content, CONFLICT)["violations"], [])
        mutated = content.replace(
            "  issues: write", "  contents: write", 1
        )
        self.assertIn(
            "workflow:contents: unexpected_elevated_permission",
            audit_permissions(mutated, CONFLICT)["violations"],
        )


if __name__ == "__main__":
    unittest.main()
