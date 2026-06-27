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

        self.assertEqual(report["schema_version"], "1.1.0")
        self.assertEqual(report["report_type"], "runtime_health_center")
        self.assertEqual(report["mode"], "local_ci_read_only")
        self.assertEqual(
            set(report["domains"]),
            {
                "ci_cd",
                "evidence_gate",
                "governance",
                "runtime_risk",
                "living_architecture",
                "environment",
                "remediation",
            },
        )
        self.assertGreaterEqual(report["maturity_percent"], 0)
        self.assertLessEqual(report["maturity_percent"], 100)
        self.assertIn(report["operational_risk"], {"low", "medium", "high"})
        self.assertIn(report["confidence_level"], {"low", "medium", "high"})
        self.assertTrue(report["next_required_actions"])
        self.assertEqual(report["gold_standard_status"]["Runtime Health Center"], "passed")
        self.assertIn(report["gold_standard_status"]["Environment Drift Detector"], {"missing", "partial", "warning", "passed"})
        self.assertIn(report["environment_drift"]["drift_level"], {"none", "low", "medium", "high"})
        self.assertEqual(
            report["gold_standard_depth"]["strategy"],
            "parar_expansao_horizontal_e_aprofundar_capacidades_existentes",
        )
        self.assertEqual(
            set(report["gold_standard_depth"]["axes"]),
            {"runtime", "observability", "operational_ux", "live_analytics", "environments", "autonomous_operation"},
        )
        self.assertIn(report["gold_standard_depth"]["overall_status"], {"passed", "warning", "partial"})
        self.assertIn("runtime_operational_evidence_graph", report)
        self.assertIn("runtime_risk_scoring", report)
        self.assertIn("public_access_validation", report)
        self.assertIn(report["public_access_validation"]["status"], {"missing", "warning", "passed"})
        self.assertIn("trilhas_padrao_ouro", report)
        self.assertTrue(report["trilhas_padrao_ouro"]["available"])
        self.assertEqual(report["trilhas_padrao_ouro"]["status"], "passed")
        self.assertEqual(report["trilhas_padrao_ouro"]["gold_standard_percent"], 100.0)
        self.assertFalse(report["pr_evidence_gate"]["duplicated"])
        self.assertLessEqual(report["maturity_percent"], report["base_maturity_percent"])

    def test_marks_missing_artifacts_without_network(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            report = build_report(Path(tmp_dir))

        self.assertTrue(all(domain["status"] == "missing" for domain in report["domains"].values()))
        self.assertEqual(report["maturity_percent"], 0)
        self.assertEqual(report["operational_risk"], "high")
        self.assertEqual(report["confidence_level"], "low")
        self.assertEqual(report["environment_drift"]["drift_level"], "high")
        self.assertEqual(report["public_access_validation"]["status"], "missing")
        self.assertEqual(report["gold_standard_depth"]["overall_status"], "partial")
        self.assertIn("runtime", report["gold_standard_depth"]["blockers"])
        self.assertFalse(report["trilhas_padrao_ouro"]["available"])

    def test_environment_drift_detector_classifies_low_for_expected_prod_delta(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docker-compose.dev.yml").write_text("""services:
  api:
    ports:
      - "${BACKEND_PORT:-8210}:8000"
    environment:
      - SDD_SPECS_PATH=/sdd
  frontend:
  nginx:
""", encoding="utf-8")
            (root / "docker-compose.test.yml").write_text("""services:
  api:
    ports:
      - "${BACKEND_PORT:-8212}:8000"
    environment:
      - DATABASE_URL=sqlite:////data/test.db
  frontend:
  nginx:
""", encoding="utf-8")
            (root / "docker-compose.prod.yml").write_text("""services:
  api:
    environment:
      - APP_ENV=production
      - ALLOW_DEMO_LOGIN=false
      - DATABASE_URL=sqlite:////data/reqsys.db
    healthcheck:
      test: ["CMD", "true"]
  frontend:
    healthcheck:
      test: ["CMD", "true"]
  nginx:
    healthcheck:
      test: ["CMD", "true"]
""", encoding="utf-8")

            report = build_report(root)

        self.assertEqual(report["environment_drift"]["drift_level"], "low")
        self.assertEqual(report["environment_drift"]["status"], "passed")
        self.assertEqual(report["operational_risk"], "high")


    def test_public_access_artifact_updates_environment_status(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "artifacts/public-access-validation").mkdir(parents=True)
            (root / "artifacts/public-access-validation/public-access-validation.json").write_text(json.dumps({
                "analytics": {
                    "total": 9,
                    "reachable": 6,
                    "expected": 6,
                    "unavailable": 3,
                    "unexpectedStatus": 3,
                    "reachablePercent": 66.67,
                    "expectedPercent": 66.67,
                    "byEnvironment": {
                        "dev": {"total": 3, "reachable": 3, "expected": 3},
                        "staging": {"total": 3, "reachable": 3, "expected": 3},
                        "prod": {"total": 3, "reachable": 0, "expected": 0},
                    },
                }
            }), encoding="utf-8")

            report = build_report(root)

        self.assertEqual(report["public_access_validation"]["status"], "warning")
        self.assertEqual(report["public_access_validation"]["environments"]["prod"]["status"], "missing")
        self.assertEqual(report["public_access_validation"]["environments"]["dev"]["status"], "passed")

    def test_cli_writes_versioned_json(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "runtime-health-report.json"
            argv = ["runtime_health_center.py", "--root", str(ROOT), "--output", str(output)]
            with patch.object(sys, "argv", argv):
                self.assertEqual(main(), 0)

            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(data["schema_version"], "1.1.0")
        self.assertIn("gold_standard_depth", data)
        self.assertEqual(data["guardrails"], ["no_network", "no_secrets", "no_deploy", "no_production_runtime_change"])


if __name__ == "__main__":
    unittest.main()
