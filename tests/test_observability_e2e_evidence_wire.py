import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.persist_observability_e2e_evidence import build_evidence_index, persist_evidence
from scripts.persist_public_runtime_evidence import infer_operational_notes
from scripts.validate_observability_e2e import (
    CheckResult,
    build_payload,
    main as validate_main,
)


class ValidateObservabilityE2eTests(unittest.TestCase):
    def test_build_payload_gate_passed_when_all_checks_ok(self):
        checks = [
            CheckResult("metrics_text_plain", "/api/runtime/metrics", True, 200, 10),
            CheckResult("dashboard_schema", "/api/runtime/dashboard", True, 200, 12),
            CheckResult("analytics_telemetry", "/api/runtime/analytics", True, 200, 11),
            CheckResult("runtime_page", "/runtime", True, 200, 9),
            CheckResult("correlation_propagation", "/api/runtime/health", True, 200, 8),
        ]
        payload = build_payload("https://example.test", "prod", checks, precondition_ok=True)
        self.assertTrue(payload["gate_passed"])
        self.assertEqual(payload["ok"], 5)
        self.assertEqual(payload["success_percentual"], 100.0)

    def test_build_payload_blocked_when_precondition_fails(self):
        checks = [
            CheckResult("strict_precondition", "/api/runtime/health", False, 404, 5, "404"),
        ]
        payload = build_payload("https://example.test", "prod", checks, precondition_ok=False)
        self.assertFalse(payload["gate_passed"])
        self.assertIn("fly_runtime_deploy_lag", payload["blocking_issues"][0])

    def test_main_returns_zero_on_localhost_with_skip_precondition(self):
        with patch("scripts.validate_observability_e2e._check_metrics") as metrics, patch(
            "scripts.validate_observability_e2e._check_dashboard"
        ) as dashboard, patch("scripts.validate_observability_e2e._check_analytics") as analytics, patch(
            "scripts.validate_observability_e2e._check_runtime_page"
        ) as runtime_page, patch(
            "scripts.validate_observability_e2e._check_correlation_propagation"
        ) as correlation:
            ok = CheckResult("x", "/x", True, 200, 1)
            metrics.return_value = ok
            dashboard.return_value = ok
            analytics.return_value = ok
            runtime_page.return_value = ok
            correlation.return_value = ok
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "out.json"
                with patch(
                    "sys.argv",
                    [
                        "validate_observability_e2e.py",
                        "--base-url",
                        "http://127.0.0.1:8000",
                        "--skip-precondition",
                        "--output",
                        str(output),
                    ],
                ):
                    code = validate_main()
                self.assertEqual(code, 0)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertTrue(payload["gate_passed"])


class PersistObservabilityE2eEvidenceTests(unittest.TestCase):
    def test_persist_writes_audit_files(self):
        validation = {
            "base_url": "https://reqsys-api.fly.dev",
            "environment": "prod",
            "gate_passed": True,
            "precondition_ok": True,
            "ok": 5,
            "total": 5,
            "success_percentual": 100.0,
            "blocking_issues": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            validation_path = root / "validation.json"
            output_dir = root / "audit/runtime"
            validation_path.write_text(json.dumps(validation), encoding="utf-8")
            index = persist_evidence(validation_path, output_dir, run_id="42")
            self.assertTrue(index["gate_passed"])
            self.assertEqual(index["increment_id"], "evidence-automation-observability-e2e")
            self.assertTrue((output_dir / "observability-e2e-evidence-index.json").exists())
            self.assertTrue((output_dir / "observability-e2e-evidence.md").exists())

    def test_build_index_notes_when_precondition_blocked(self):
        index = build_evidence_index(
            {"gate_passed": False, "precondition_ok": False, "blocking_issues": ["404"]},
            repository="example/repo",
            run_id="1",
            event_name="workflow_run",
            sha="abc",
        )
        self.assertEqual(index["operational_notes"][0]["id"], "fly_runtime_deploy_lag")
        self.assertEqual(index["operational_notes"][0]["next_increment"], "fly-runtime-p0-deploy")


class PublicRuntimeStrictReadyNoteTests(unittest.TestCase):
    def test_infer_strict_ready_note_when_gate_passes(self):
        validation = {
            "results": [
                {"endpoint": "/health", "ok": True, "status_code": 200},
                {"endpoint": "/api/runtime/health", "ok": True, "status_code": 200},
                {"endpoint": "/api/runtime/readiness", "ok": True, "status_code": 200},
                {"endpoint": "/api/runtime/liveness", "ok": True, "status_code": 200},
            ],
            "readiness": {"blocking_issues": []},
        }
        notes = infer_operational_notes(validation, validation["readiness"], strict_gate_passed=True)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["id"], "public_runtime_strict_ready")
        self.assertEqual(notes[0]["next_increment"], "evidence-automation-observability-e2e")


if __name__ == "__main__":
    unittest.main()
