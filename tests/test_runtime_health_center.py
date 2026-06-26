import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.runtime_health_center import build_report, main  # noqa: E402


class RuntimeHealthCenterTests(unittest.TestCase):
    def test_contract_contains_required_domains(self):
        report = build_report(ROOT)

        self.assertEqual(report["schema_version"], "1.0.0")
        self.assertEqual(report["report_type"], "runtime_health_center")
        self.assertEqual(report["mode"], "local_ci_read_only")
        self.assertEqual(
            set(report["domains"]),
            {
                "ci_cd",
                "living_architecture",
                "evidence",
                "environment",
                "governance",
                "remediation",
            },
        )
        self.assertGreaterEqual(report["maturity_percent"], 0)
        self.assertLessEqual(report["maturity_percent"], 100)
        self.assertIn(report["operational_risk"], {"low", "medium", "high"})
        self.assertIn(report["confidence_level"], {"low", "medium", "high"})
        self.assertTrue(report["next_required_actions"])

    def test_marks_missing_artifacts_without_network(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            report = build_report(Path(tmp_dir))

        self.assertTrue(all(domain["status"] == "missing" for domain in report["domains"].values()))
        self.assertEqual(report["maturity_percent"], 0)
        self.assertEqual(report["operational_risk"], "high")
        self.assertEqual(report["confidence_level"], "low")

    def test_cli_writes_versioned_json(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "runtime-health-report.json"
            argv = ["runtime_health_center.py", "--root", str(ROOT), "--output", str(output)]
            with patch.object(sys, "argv", argv):
                self.assertEqual(main(), 0)

            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(data["schema_version"], "1.0.0")
        self.assertEqual(data["guardrails"], ["no_network", "no_secrets", "no_deploy", "no_production_runtime_change"])


if __name__ == "__main__":
    unittest.main()
