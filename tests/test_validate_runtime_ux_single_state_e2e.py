from __future__ import annotations

import unittest

from scripts.validate_runtime_ux_single_state_e2e import validate_single_state


class RuntimeUxSingleStateE2ETest(unittest.TestCase):
    def base(self):
        return {
            "contract": "reqsys-single-state-runtime-ux",
            "decision": {
                "status": "RUNTIME_UX_CORRELATION_PENDING",
                "mode": "advisory",
                "production_blocker": False,
                "promotion_allowed": False,
                "human_approval_required": True,
                "production_ready_candidate": False,
            },
            "evidence": None,
        }

    def test_pending_is_safe_and_non_blocking(self):
        result = validate_single_state(self.base())
        self.assertEqual(result["status"], "E2E_CORRELATION_PENDING")
        self.assertFalse(result["promotion_allowed"])
        self.assertTrue(result["human_approval_required"])

    def test_verified_requires_same_run_environment_and_sha(self):
        value = self.base()
        value["decision"]["status"] = "RUNTIME_UX_EVIDENCE_VERIFIED"
        value["evidence"] = {
            "environment": "prod",
            "source_run_id": "12345",
            "source_head_sha": "abcdef1234567890",
            "observed_sha": "abcdef1",
        }
        result = validate_single_state(value)
        self.assertEqual(result["status"], "E2E_CORRELATION_VERIFIED")
        self.assertTrue(result["checks"]["correlation_verified"])

    def test_verified_rejects_sha_divergence(self):
        value = self.base()
        value["decision"]["status"] = "RUNTIME_UX_EVIDENCE_VERIFIED"
        value["evidence"] = {
            "environment": "stg",
            "source_run_id": "12345",
            "source_head_sha": "abcdef1",
            "observed_sha": "9876543",
        }
        with self.assertRaisesRegex(ValueError, "identidade completa"):
            validate_single_state(value)

    def test_guardrails_cannot_be_relaxed(self):
        value = self.base()
        value["decision"]["promotion_allowed"] = True
        with self.assertRaisesRegex(ValueError, "promotion_allowed"):
            validate_single_state(value)


if __name__ == "__main__":
    unittest.main()
