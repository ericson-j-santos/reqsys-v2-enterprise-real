import unittest

from scripts.build_runtime_ux_from_homologation import build_runtime_ux_evidence


class RuntimeUxFromHomologationTests(unittest.TestCase):
    def evidence(self):
        return {
            "contract": "fly-environment-homologation-gate",
            "ok": True,
            "environment": "stg",
            "observed_sha": "abcdef123456",
            "correlation_id": "corr-1",
            "generated_at_epoch": 1_700_000_000,
            "probes": [
                {"name": "health", "critical": True, "ok": True, "duration_ms": 100},
                {"name": "journey", "critical": True, "ok": True, "duration_ms": 300},
                {"name": "optional", "critical": False, "ok": False, "duration_ms": 900},
            ],
        }

    def test_builds_runtime_ux_with_same_run_identity(self):
        result = build_runtime_ux_evidence(
            self.evidence(),
            source_run_id="123",
            source_head_sha="abcdef1234567890",
            source_workflow="Fly Environment Homologation Gate",
        )[0]
        self.assertEqual(result["source_run_id"], "123")
        self.assertEqual(result["environment"], "stg")
        self.assertEqual(result["source_head_sha"], "abcdef123456")
        self.assertEqual(result["recovery_rate"], 100.0)
        self.assertEqual(result["average_recovery_seconds"], 0.2)
        self.assertTrue(result["ux_100_ready"])
        self.assertFalse(result["production_blocker"])

    def test_rejects_failed_homologation(self):
        evidence = self.evidence()
        evidence["ok"] = False
        with self.assertRaisesRegex(ValueError, "reprovada"):
            build_runtime_ux_evidence(
                evidence,
                source_run_id="123",
                source_head_sha="abcdef1234567890",
                source_workflow="Fly Environment Homologation Gate",
            )

    def test_calculates_partial_recovery(self):
        evidence = self.evidence()
        evidence["probes"][1]["ok"] = False
        result = build_runtime_ux_evidence(
            evidence,
            source_run_id="123",
            source_head_sha="abcdef1234567890",
            source_workflow="Fly Environment Homologation Gate",
        )[0]
        self.assertEqual(result["recovery_rate"], 50.0)
        self.assertFalse(result["ux_100_ready"])

    def test_rejects_missing_critical_journeys(self):
        evidence = self.evidence()
        evidence["probes"] = [{"critical": False, "ok": True, "duration_ms": 1}]
        with self.assertRaisesRegex(ValueError, "probe crítico"):
            build_runtime_ux_evidence(
                evidence,
                source_run_id="123",
                source_head_sha="abcdef1234567890",
                source_workflow="Fly Environment Homologation Gate",
            )


if __name__ == "__main__":
    unittest.main()
