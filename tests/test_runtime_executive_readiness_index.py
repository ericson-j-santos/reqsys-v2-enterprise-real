import unittest

from scripts.build_runtime_executive_index import build_runtime_executive_index


class RuntimeExecutiveReadinessIndexTests(unittest.TestCase):
    def test_executive_readiness_gate_is_top_level_runtime_index_signal(self):
        payload = build_runtime_executive_index(
            health={
                "repo": "example/repo",
                "overall_status": "passed",
                "health_score": 100,
                "public_runtime_readiness": {
                    "available": True,
                    "operational_status": "passed",
                    "readiness_percent": 100,
                },
            },
            merge_index={
                "repo": "example/repo",
                "merge_intelligence": {
                    "risk": "low",
                    "parallel_safe": True,
                    "mergeability_score": 100,
                    "recommendation": "merge_imediato",
                    "confidence": "high",
                },
            },
            lane_priority={"ranking": [{"parallelism": "safe"}]},
            repo="example/repo",
            evidence_gate_report={"gate": {"status": "passed", "failures": [], "required_workflows": []}},
            finalization_report={"status": "passed", "final_score": 100, "indicators": []},
            runtime_validation={"overall_state": "green", "validation_score": 100, "operational_risk_percent": 0, "production_ready": True},
            executive_readiness_gate={
                "executive_readiness": {
                    "ready_for_production": True,
                    "overall_state": "green",
                    "score": 100,
                    "risk_percent": 0,
                    "blockers": [],
                    "decision": "READY_FOR_PRODUCTION",
                },
                "domains": {"ci_cd": {"production_blocker": True}},
            },
        )

        self.assertEqual(payload["schema_version"], "1.2.0")
        self.assertTrue(payload["summary"]["production_ready"])
        self.assertEqual(payload["summary"]["executive_readiness_decision"], "READY_FOR_PRODUCTION")
        self.assertIn("executive_readiness", payload["cards"])
        self.assertTrue(payload["cards"]["executive_readiness"]["ready_for_production"])
        self.assertEqual(payload["cards"]["executive_readiness"]["risk"], "low")
        self.assertIn("executive_readiness_gate", payload["links"])
        self.assertIn("executive_readiness_gate_precedence_for_production_decision", payload["guardrails"])

    def test_blocked_executive_readiness_controls_summary_risk(self):
        payload = build_runtime_executive_index(
            health={"overall_status": "passed", "health_score": 100},
            merge_index={"merge_intelligence": {"risk": "low", "mergeability_score": 100, "recommendation": "merge_imediato"}},
            lane_priority={},
            evidence_gate_report={"gate": {"status": "passed", "failures": []}},
            finalization_report={"status": "passed", "final_score": 100},
            runtime_validation={"overall_state": "green", "validation_score": 100, "operational_risk_percent": 0, "production_ready": True},
            executive_readiness_gate={
                "executive_readiness": {
                    "ready_for_production": False,
                    "overall_state": "red",
                    "score": 82,
                    "risk_percent": 18,
                    "blockers": ["seguranca_red"],
                    "decision": "BLOCKED_FOR_PRODUCTION",
                }
            },
        )

        self.assertFalse(payload["summary"]["production_ready"])
        self.assertEqual(payload["summary"]["status"], "critical")
        self.assertEqual(payload["summary"]["risk"], "high")
        self.assertEqual(payload["cards"]["executive_readiness"]["blocker_count"], 1)


if __name__ == "__main__":
    unittest.main()
