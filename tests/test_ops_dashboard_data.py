import unittest

from scripts.generate_ops_dashboard_data import build_dashboard_payload


class OpsDashboardDataTests(unittest.TestCase):
    def test_runtime_drilldown_and_incident_timeline_contract(self):
        watchdog = {
            "overall_status": "warning",
            "warning_count": 1,
            "critical_failure_count": 0,
            "results": [
                {
                    "name": "CI verde PR #323",
                    "status": "warning",
                    "severity": "warning",
                    "workflow": "ci-enterprise-fast",
                    "domain": "ci_cd",
                    "evidence": {"run": "local"},
                }
            ],
        }
        runtime = {
            "maturity_percent": 82,
            "confidence_level": "medium",
            "operational_risk": "medium",
            "guardrails": ["no_network", "no_secrets"],
            "next_required_actions": ["Revisar domínio ci_cd."],
            "runtime_risk_scoring": {"status": "warning", "drift_level": "low"},
            "environment_drift": {"drift_level": "low", "findings": [{"severity": "low", "message": "delta esperado"}]},
            "gold_standard_status": {"Runtime Health Center": "passed"},
            "ingested_artifacts": {"artifacts": [{"id": "runtime_health_validator", "available": True, "status": "passed"}]},
            "domains": {
                "ci_cd": {
                    "status": "warning",
                    "score": 70,
                    "signals_available": 1,
                    "signals_total": 2,
                    "signals": [
                        {"id": "workflow", "available": True, "status": "passed"},
                        {"id": "report", "available": False, "status": "missing"},
                    ],
                },
                "governance": {"status": "passed", "score": 100, "signals_available": 1, "signals_total": 1, "signals": []},
            },
        }
        evidence_graph = {"nodes": [{"id": "pr-323", "domain": "governance", "status": "passed", "workflow": "ops-dashboard", "pr": 323}]}

        public_runtime = {
            "base_url": "https://reqsys-api.fly.dev",
            "readiness": {
                "environment": "prod",
                "operational_status": "partial",
                "readiness_percent": 75,
                "response_time": 321,
                "dashboard_ready": True,
                "login_ready": False,
                "api_ready": True,
                "runtime_ready": True,
                "evidence_ready": True,
                "blocking_issues": ["/api/runtime/readiness: 503"],
            },
            "checks": {"frontend_loading": True, "assets": True},
        }

        delivery_finalization = {
            "final_score": 99.54,
            "residual_gap": 0.46,
            "status": "passed",
            "indicators": [
                {"id": "ci", "name": "CI verde", "status": "passed", "score": 100, "gap": 0, "evidence": {"run": "local"}},
                {"id": "docs", "name": "Runbook", "status": "warning", "score": 95, "gap": 5},
            ],
        }

        payload = build_dashboard_payload(watchdog, "example/repo", runtime, evidence_graph, public_runtime, {}, delivery_finalization)

        self.assertEqual(payload["schema_version"], "1.3.0")
        self.assertTrue(payload["runtime_sources"]["runtime_health_report_available"])
        self.assertTrue(payload["runtime_sources"]["runtime_operational_evidence_graph_available"])
        self.assertTrue(payload["runtime_sources"]["public_runtime_validation_available"])
        self.assertTrue(payload["runtime_sources"]["delivery_finalization_report_available"])
        self.assertTrue(payload["delivery_finalization"]["available"])
        self.assertEqual(payload["delivery_finalization"]["final_score"], 99.54)
        self.assertEqual(payload["delivery_finalization"]["residual_gap"], 0.46)
        self.assertEqual(payload["delivery_finalization"]["indicator_count"], 2)
        self.assertEqual(payload["delivery_finalization"]["passed_indicator_count"], 1)
        self.assertEqual(payload["public_runtime_readiness"]["operational_status"], "partial")
        self.assertEqual(payload["public_runtime_readiness"]["readiness_percent"], 75)
        self.assertEqual({item["id"] for item in payload["runtime_domain_drilldowns"]}, {"ci_cd", "governance"})
        ci_domain = next(item for item in payload["runtime_domain_drilldowns"] if item["id"] == "ci_cd")
        self.assertEqual(ci_domain["health"]["maturity_percent"], 82)
        self.assertEqual(len(ci_domain["evidence"]), 1)
        self.assertEqual(len(ci_domain["missing_evidence"]), 1)
        self.assertGreaterEqual(len(payload["incident_timeline"]), 4)
        self.assertIn("323", {str(item["pr"]) for item in payload["incident_timeline"]})
        self.assertIn("runtime_health_report", {item["source"] for item in payload["incident_timeline"]})

    def test_delivery_finalization_fallback_is_safe_when_artifact_missing(self):
        payload = build_dashboard_payload({"overall_status": "unknown", "results": []}, "example/repo")

        self.assertFalse(payload["runtime_sources"]["delivery_finalization_report_available"])
        self.assertFalse(payload["delivery_finalization"]["available"])
        self.assertEqual(payload["delivery_finalization"]["status"], "unknown")
        self.assertEqual(payload["delivery_finalization"]["indicator_count"], 0)
        self.assertIn("Fallback seguro", payload["delivery_finalization"]["guardrail"])


if __name__ == "__main__":
    unittest.main()
