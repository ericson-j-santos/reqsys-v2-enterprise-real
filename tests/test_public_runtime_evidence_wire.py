import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_ops_dashboard_data import _resolve_public_runtime, build_dashboard_payload
from scripts.persist_public_runtime_evidence import build_evidence_index, persist_evidence


class PersistPublicRuntimeEvidenceTests(unittest.TestCase):
    def test_persist_writes_audit_files_with_index(self):
        validation = {
            "schema_version": "1.3.0",
            "base_url": "https://reqsys-api.fly.dev",
            "environment": "prod",
            "ok": 3,
            "total": 4,
            "success_percentual": 75.0,
            "readiness": {
                "operational_status": "partial",
                "readiness_percent": 75.0,
                "blocking_issues": ["/api/runtime/liveness: 503"],
            },
        }
        readiness = validation["readiness"]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            validation_path = root / "validation.json"
            readiness_path = root / "readiness.json"
            output_dir = root / "audit/runtime"
            validation_path.write_text(json.dumps(validation), encoding="utf-8")
            readiness_path.write_text(json.dumps(readiness), encoding="utf-8")

            index = persist_evidence(
                validation_path,
                readiness_path,
                output_dir,
                repository="example/repo",
                run_id="12345",
                event_name="workflow_dispatch",
                sha="abc123",
                strict_gate_passed=False,
            )

            self.assertEqual(index["run_id"], "12345")
            self.assertFalse(index["strict_gate_passed"])
            self.assertEqual(index["summary"]["operational_status"], "partial")
            self.assertTrue((output_dir / "public-runtime-validation.json").exists())
            self.assertTrue((output_dir / "ops-readiness-report.json").exists())
            self.assertTrue((output_dir / "public-runtime-evidence-index.json").exists())
            self.assertTrue((output_dir / "public-runtime-evidence.md").exists())

    def test_build_evidence_index_contract(self):
        index = build_evidence_index(
            {"base_url": "https://example.test", "ok": 4, "total": 4, "success_percentual": 100.0},
            {"operational_status": "healthy", "readiness_percent": 100.0},
            repository="example/repo",
            run_id="1",
            event_name="schedule",
            sha="deadbeef",
            strict_gate_passed=True,
        )
        self.assertEqual(index["contract"], "public-runtime-evidence-index")
        self.assertTrue(index["strict_gate_passed"])


class OpsDashboardPublicRuntimeResolutionTests(unittest.TestCase):
    def test_prefers_audit_path_over_artifacts_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path = root / "audit/runtime/public-runtime-validation.json"
            artifacts_path = root / "artifacts/runtime/public-runtime-validation.json"
            index_path = root / "audit/runtime/public-runtime-evidence-index.json"
            audit_path.parent.mkdir(parents=True)
            artifacts_path.parent.mkdir(parents=True)
            audit_path.write_text(
                json.dumps({"base_url": "https://audit.test", "readiness": {"operational_status": "healthy"}}),
                encoding="utf-8",
            )
            artifacts_path.write_text(
                json.dumps({"base_url": "https://fallback.test", "readiness": {"operational_status": "degraded"}}),
                encoding="utf-8",
            )
            index_path.write_text(json.dumps({"run_id": "999", "generated_at": "2026-06-27T00:00:00Z"}), encoding="utf-8")

            data, provenance = _resolve_public_runtime(audit_path, artifacts_path, index_path)

            self.assertEqual(data["base_url"], "https://audit.test")
            self.assertFalse(provenance["source_fallback"])
            self.assertEqual(provenance["run_id"], "999")

    def test_uses_artifacts_fallback_when_audit_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path = root / "audit/runtime/public-runtime-validation.json"
            artifacts_path = root / "artifacts/runtime/public-runtime-validation.json"
            artifacts_path.parent.mkdir(parents=True)
            artifacts_path.write_text(
                json.dumps({"base_url": "https://fallback.test", "readiness": {"operational_status": "degraded"}}),
                encoding="utf-8",
            )

            data, provenance = _resolve_public_runtime(audit_path, artifacts_path)

            self.assertEqual(data["base_url"], "https://fallback.test")
            self.assertTrue(provenance["source_fallback"])

    def test_dashboard_marks_public_runtime_unavailable_without_sources(self):
        payload = build_dashboard_payload({"overall_status": "unknown", "results": []}, "example/repo")

        self.assertFalse(payload["runtime_sources"]["public_runtime_validation_available"])
        self.assertTrue(payload["runtime_sources"]["public_runtime_source_fallback"])
        self.assertFalse(payload["public_runtime_readiness"]["available"])


if __name__ == "__main__":
    unittest.main()
