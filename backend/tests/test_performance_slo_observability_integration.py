import importlib.util
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "integrate_performance_slo_observability.py"
spec = importlib.util.spec_from_file_location("performance_slo_observability", MODULE_PATH)
adapter = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(adapter)

NOW = datetime(2026, 8, 25, 20, 0, tzinfo=UTC)


def sample_report(status="passed", generated_at="2026-08-25T18:00:00Z", budget=70.0, sustained="stable", points=0):
    breach = status == "blocked"
    warning = status == "watch"
    return {
        "schema_version": "1.0.0",
        "source": "performance-slo-error-budget",
        "generated_at": generated_at,
        "environment": "prod",
        "correlation_id": "performance-slo-12345",
        "status": status,
        "operational_risk": "high" if breach else ("medium" if warning else "low"),
        "summary": {
            "slo_count": 2,
            "mature_slo_count": 2,
            "breach_count": 1 if breach else 0,
            "warning_count": 1 if warning else 0,
            "met_count": 1 if breach or warning else 2,
            "no_data_count": 0,
            "point_regressions_total": points,
            "sustained_degradations_total": 1 if sustained == "degraded" else 0,
        },
        "slos": [
            {
                "slo_id": "performance_api_latency",
                "name": "Latency",
                "status": "breach" if breach else "met",
                "mature": True,
                "actual_percent": 94 if breach else 99,
                "target_percent": 95,
                "error_budget_remaining_percent": budget,
                "eligible_measurements": 10,
                "bad_measurements": 1,
            },
            {
                "slo_id": "performance_browser_runtime",
                "name": "Browser",
                "status": "met",
                "mature": True,
                "actual_percent": 100,
                "target_percent": 95,
                "error_budget_remaining_percent": 100,
                "eligible_measurements": 5,
                "bad_measurements": 0,
            },
        ],
        "sustained_degradation": {
            "status": sustained,
            "required_consecutive": 3,
            "findings": [{}] if sustained == "degraded" else [],
        },
    }


def provenance(state="available", conclusion="success", expected=True, found=True):
    return {
        "schema_version": "1.0.0",
        "state": state,
        "source_workflow_run_id": "777",
        "source_workflow_conclusion": conclusion,
        "source_event": "workflow_run",
        "source_head_branch": "main",
        "source_head_sha": "abc",
        "source_url": "https://github.com/o/r/actions/runs/777",
        "artifact_expected": expected,
        "artifact_found": found,
        "artifact_name": "performance-slo-evidence" if found else None,
    }


class PerformanceSloObservabilityTests(unittest.TestCase):
    def test_passed_is_healthy_with_worst_budget(self):
        value = adapter.normalize_performance_slo(sample_report(budget=70), provenance(), now=NOW)
        self.assertEqual(value["state"], "healthy")
        self.assertEqual(value["error_budget"]["worst_remaining_percent"], 70)
        self.assertEqual(value["trend"]["direction"], "stable")
        self.assertFalse(value["alert"]["should_alert"])
        self.assertEqual(value["dynamic_performance_run_id"], "12345")

    def test_blocked_escalates_hub_and_alert(self):
        normalized = adapter.normalize_performance_slo(
            sample_report("blocked", budget=0, sustained="degraded"),
            provenance(conclusion="failure"),
            now=NOW,
        )
        hub = {
            "status": "healthy",
            "operational_risk": "low",
            "sources": {},
            "pareto_increment": {},
            "correlation_chain": [],
            "governed_alert": {"alert_level": "INFO", "should_alert": False},
            "recommended_actions": ["Base"],
        }
        adapter.inject_hub(hub, normalized)
        adapter.inject_hub(hub, normalized)
        self.assertEqual(hub["status"], "degraded")
        self.assertEqual(hub["operational_risk"], "high")
        self.assertEqual(hub["governed_alert"]["alert_type"], "PERFORMANCE_SLO_BREACH")
        self.assertEqual(len([x for x in hub["correlation_chain"] if x["event"] == "performance_slo_evidence"]), 1)

    def test_stale_evidence_never_becomes_healthy(self):
        value = adapter.normalize_performance_slo(
            sample_report(generated_at="2026-08-20T00:00:00Z"), provenance(), now=NOW, max_age_hours=36
        )
        self.assertEqual(value["state"], "stale")
        self.assertFalse(value["current"])
        self.assertTrue(value["alert"]["should_alert"])

    def test_not_applicable_is_neutral(self):
        value = adapter.normalize_performance_slo(
            {}, provenance("not_applicable", expected=False, found=False), now=NOW
        )
        self.assertEqual(value["state"], "not_applicable")
        self.assertFalse(value["alert"]["should_alert"])
        self.assertEqual(value["operational_risk"], "low")

    def test_expected_missing_artifact_is_fail_closed_signal(self):
        value = adapter.normalize_performance_slo(
            {}, provenance("artifact_missing", expected=True, found=False), now=NOW
        )
        self.assertEqual(value["state"], "artifact_missing")
        self.assertEqual(value["operational_risk"], "high")
        self.assertTrue(value["alert"]["should_alert"])

    def test_dashboard_check_is_visible_and_idempotent(self):
        normalized = adapter.normalize_performance_slo(sample_report("watch", budget=20, points=1), provenance(), now=NOW)
        combined = adapter.combine_slo_evidence(
            {"source": "operational-slo-evidence", "summary": {"slo_count": 3}}, normalized, NOW
        )
        health = {"checks": [{"name": "Other"}], "runtime_sources": {}}
        adapter.inject_dashboard_health(health, normalized, combined)
        adapter.inject_dashboard_health(health, normalized, combined)
        checks = [x for x in health["checks"] if x.get("id") == adapter.CHECK_ID]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["status"], "warning")
        self.assertEqual(checks[0]["evidence"]["error_budget_remaining_percent"], 20)
        self.assertEqual(health["slo_evidence"]["operational"]["source"], "operational-slo-evidence")

    def test_markdown_and_cli_are_idempotent(self):
        normalized = adapter.normalize_performance_slo(sample_report(), provenance(), now=NOW)
        markdown = adapter.inject_markdown("# Hub\n", normalized)
        markdown = adapter.inject_markdown(markdown, normalized)
        self.assertEqual(markdown.count(adapter.MARKER_START), 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "perf.json").write_text(json.dumps(sample_report()), encoding="utf-8")
            (root / "prov.json").write_text(json.dumps(provenance()), encoding="utf-8")
            (root / "health.json").write_text(json.dumps({"checks": []}), encoding="utf-8")
            (root / "slo.json").write_text(json.dumps({"source": "operational-slo-evidence"}), encoding="utf-8")
            rc = adapter.main([
                "--performance-slo", str(root / "perf.json"),
                "--provenance", str(root / "prov.json"),
                "--dashboard-health", str(root / "health.json"),
                "--dashboard-slo", str(root / "slo.json"),
                "--output", str(root / "out.json"),
                "--now", "2026-08-25T20:00:00Z",
            ])
            self.assertEqual(rc, 0)
            self.assertTrue((root / "out.json").exists())

    def test_workflow_contract_keeps_deploy_manual_and_adds_post_merge_evidence(self):
        p0 = (ROOT / ".github/workflows/fly-runtime-p0.yml").read_text(encoding="utf-8")
        hub = (ROOT / ".github/workflows/operational-observability-hub.yml").read_text(encoding="utf-8")
        dashboard = (ROOT / ".github/workflows/ops-dashboard.yml").read_text(encoding="utf-8")
        self.assertIn("push:", p0)
        self.assertIn("branches: [main]", p0)
        self.assertIn("github.event_name == 'workflow_dispatch'", p0)
        self.assertIn("Performance SLO Error Budget Gate", hub)
        self.assertIn("collect-performance-slo-evidence", hub)
        self.assertIn("integrate_performance_slo_observability.py", hub)
        self.assertIn("Performance SLO Error Budget Gate", dashboard)
        self.assertIn("collect-performance-slo-evidence", dashboard)
        self.assertIn("integrate_performance_slo_observability.py", dashboard)


if __name__ == "__main__":
    unittest.main()
