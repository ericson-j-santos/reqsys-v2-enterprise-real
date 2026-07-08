import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_security_executive_summary import build_summary


class SecurityExecutiveSummaryTest(unittest.TestCase):
    def test_builds_green_summary_with_sbom_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sbom_dir = root / "artifacts/security-scanners/sbom"
            sbom_dir.mkdir(parents=True)
            (sbom_dir / "reqsys-sbom.cyclonedx.json").write_text(
                json.dumps({"components": [{"name": "a"}, {"name": "b"}]}),
                encoding="utf-8",
            )
            pip_dir = root / "artifacts/security-scanners/pip-audit"
            pip_dir.mkdir(parents=True)
            (pip_dir / "requirements.json").write_text(json.dumps({"dependencies": []}), encoding="utf-8")
            npm_dir = root / "artifacts/security-scanners/npm-audit"
            npm_dir.mkdir(parents=True)
            (npm_dir / "root.json").write_text(
                json.dumps({"metadata": {"dependencies": {"total": 2}, "vulnerabilities": {}}}),
                encoding="utf-8",
            )

            summary = build_summary("repo/test", "main", root, "cid-1")

            self.assertEqual(summary["kind"], "security_executive_summary")
            self.assertEqual(summary["overall"]["state"], "yellow")
            self.assertFalse(summary["overall"]["production_blocked"])
            self.assertIn("gitleaks", summary["overall"]["missing_scanners"])
            self.assertEqual(summary["scanners"]["cyclonedx-sbom"]["components_inventory"], 2)

    def test_blocks_when_gitleaks_reports_findings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gitleaks_dir = root / "artifacts/security-scanners/gitleaks"
            gitleaks_dir.mkdir(parents=True)
            (gitleaks_dir / "gitleaks-report.json").write_text(
                json.dumps([{"RuleID": "generic-api-key"}]),
                encoding="utf-8",
            )

            summary = build_summary("repo/test", "main", root, "cid-2")

            self.assertEqual(summary["overall"]["state"], "red")
            self.assertEqual(summary["overall"]["decision"], "BLOCKED_SECURITY_CRITICAL")
            self.assertTrue(summary["overall"]["production_blocked"])
            self.assertEqual(summary["totals"]["severity"]["critical"], 1)

    def test_reads_npm_audit_metadata_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            npm_dir = root / "artifacts/security-scanners/npm-audit"
            npm_dir.mkdir(parents=True)
            (npm_dir / "frontend.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "dependencies": {"total": 10},
                            "vulnerabilities": {"critical": 0, "high": 1, "medium": 2, "low": 3},
                        }
                    }
                ),
                encoding="utf-8",
            )

            summary = build_summary("repo/test", "main", root, "cid-3")

            self.assertEqual(summary["scanners"]["npm-audit"]["dependencies_evaluated"], 10)
            self.assertEqual(summary["totals"]["severity"]["high"], 1)
            self.assertEqual(summary["overall"]["decision"], "REVIEW_SECURITY_BACKLOG")


if __name__ == "__main__":
    unittest.main()
