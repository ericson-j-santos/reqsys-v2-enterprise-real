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

        payload = build_dashboard_payload(watchdog, "example/repo", runtime, evidence_graph)

        self.assertEqual(payload["schema_version"], "1.1.0")
        self.assertTrue(payload["runtime_sources"]["runtime_health_report_available"])
        self.assertTrue(payload["runtime_sources"]["runtime_operational_evidence_graph_available"])
        self.assertEqual({item["id"] for item in payload["runtime_domain_drilldowns"]}, {"ci_cd", "governance"})
        ci_domain = next(item for item in payload["runtime_domain_drilldowns"] if item["id"] == "ci_cd")
        self.assertEqual(ci_domain["health"]["maturity_percent"], 82)
        self.assertEqual(len(ci_domain["evidence"]), 1)
        self.assertEqual(len(ci_domain["missing_evidence"]), 1)
        self.assertGreaterEqual(len(payload["incident_timeline"]), 4)
        self.assertIn("323", {str(item["pr"]) for item in payload["incident_timeline"]})
        self.assertIn("runtime_health_report", {item["source"] for item in payload["incident_timeline"]})


if __name__ == "__main__":
    unittest.main()
