import unittest

from scripts.build_reqsys_e2e_executive_indicator import (
    PENDING,
    VERIFIED,
    build_indicator,
)


def base_payload(status=VERIFIED):
    return {
        "contract": "reqsys-runtime-ux-single-state-e2e-gate",
        "status": status,
        "checks": {
            "contract_valid": True,
            "guardrails_preserved": True,
            "correlation_verified": status == VERIFIED,
            "environment_valid": status == VERIFIED,
            "run_identity_present": status == VERIFIED,
            "sha_consistent": status == VERIFIED,
        },
        "production_ready_candidate": True,
        "promotion_allowed": False,
        "human_approval_required": True,
        "production_blocker": False,
        "mode": "advisory",
    }


class ExecutiveIndicatorTests(unittest.TestCase):
    def test_verified_evidence_elevates_confidence_only(self):
        result = build_indicator(base_payload())
        self.assertEqual(result["official_indicator"], VERIFIED)
        self.assertTrue(result["evidence_accepted"])
        self.assertEqual(result["confidence"]["score"], 100)
        self.assertEqual(result["production_readiness"]["score"], 95)
        self.assertFalse(result["production_readiness"]["promotion_allowed"])
        self.assertTrue(result["production_readiness"]["human_approval_required"])

    def test_pending_does_not_elevate_confidence(self):
        result = build_indicator(base_payload(PENDING))
        self.assertEqual(result["official_indicator"], PENDING)
        self.assertFalse(result["evidence_accepted"])
        self.assertEqual(result["confidence"]["score"], 60)
        self.assertEqual(result["operational_risk"], "medium")

    def test_verified_requires_all_identity_checks(self):
        payload = base_payload()
        payload["checks"]["sha_consistent"] = False
        with self.assertRaisesRegex(ValueError, "checks completos"):
            build_indicator(payload)

    def test_guardrails_cannot_be_relaxed(self):
        payload = base_payload()
        payload["promotion_allowed"] = True
        with self.assertRaisesRegex(ValueError, "guardrails"):
            build_indicator(payload)

    def test_contract_must_be_authorized(self):
        payload = base_payload()
        payload["contract"] = "unknown"
        with self.assertRaisesRegex(ValueError, "contrato E2E"):
            build_indicator(payload)


if __name__ == "__main__":
    unittest.main()
