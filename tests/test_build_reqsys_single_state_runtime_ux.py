import unittest

from scripts.build_reqsys_single_state_runtime_ux import build_single_state


class ReqSysSingleStateRuntimeUxTests(unittest.TestCase):
    def runtime(self, **overrides):
        value = {
            "contract": "reqsys-runtime-environment-evidence",
            "evidence_source": "runtime",
            "attestation_provider": "github-artifact-attestations",
            "environment": "stg",
            "source_run_id": "100",
            "source_head_sha": "abcdef1234567890",
            "observed_sha": "abcdef123456",
            "blocking_issues": [],
            "evidence_sha256": "a" * 64,
            "correlation_id": "corr-100",
        }
        value.update(overrides)
        return value

    def ux(self, **overrides):
        value = {
            "evidence_source": "runtime",
            "environment": "stg",
            "source_run_id": "100",
            "source_head_sha": "abcdef1234567890",
            "recovery_rate": 85,
            "average_recovery_seconds": 20,
            "ux_100_ready": True,
        }
        value.update(overrides)
        return value

    def test_correlates_by_run_environment_and_sha(self):
        result = build_single_state([self.runtime()], [self.ux()])
        self.assertEqual(result["decision"]["status"], "RUNTIME_UX_EVIDENCE_VERIFIED")
        self.assertEqual(result["correlated_evidence_count"], 1)
        self.assertFalse(result["decision"]["promotion_allowed"])
        self.assertFalse(result["decision"]["production_ready_candidate"])

    def test_keeps_pending_when_run_differs(self):
        result = build_single_state([self.runtime()], [self.ux(source_run_id="101")])
        self.assertEqual(result["decision"]["status"], "RUNTIME_UX_CORRELATION_PENDING")
        self.assertIsNone(result["evidence"])

    def test_rejects_synthetic_ux(self):
        result = build_single_state([self.runtime()], [self.ux(evidence_source="synthetic")])
        self.assertEqual(result["ux_runtime_evidence_count"], 0)
        self.assertEqual(result["correlated_evidence_count"], 0)

    def test_marks_prod_candidate_but_never_auto_promotes(self):
        result = build_single_state(
            [self.runtime(environment="prod")],
            [self.ux(environment="prod")],
        )
        self.assertTrue(result["decision"]["production_ready_candidate"])
        self.assertFalse(result["decision"]["promotion_allowed"])
        self.assertTrue(result["decision"]["human_approval_required"])

    def test_prod_candidate_requires_ux_thresholds(self):
        result = build_single_state(
            [self.runtime(environment="prod")],
            [self.ux(environment="prod", recovery_rate=79, average_recovery_seconds=31)],
        )
        self.assertFalse(result["decision"]["production_ready_candidate"])


if __name__ == "__main__":
    unittest.main()
