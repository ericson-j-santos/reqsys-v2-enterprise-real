import unittest

from scripts.build_parallelism_approval_receipt import build


class ParallelismApprovalReceiptTests(unittest.TestCase):
    def base_request(self):
        return {
            "schema_version": "1.0.0",
            "contract": "reqsys-parallelism-change-request",
            "request_status": "AWAITING_HUMAN_APPROVAL",
            "current_stage": 1,
            "recommended_stage": 2,
            "change_type": "INCREASE_ONE_STAGE",
            "execution": {
                "automatic_application_allowed": False,
                "applied": False,
            },
            "production": {"promotion_allowed": False},
        }

    def build_receipt(self, request=None, decision="APPROVE"):
        return build(
            request or self.base_request(),
            decision=decision,
            actor="governance-owner",
            reason="Three stable windows confirmed",
            source_artifact_id="12345",
            repository="example/reqsys",
            run_id="67890",
        )

    def test_approval_creates_auditable_receipt_without_applying_change(self):
        receipt = self.build_receipt()

        self.assertEqual(receipt["decision_status"], "APPROVED")
        self.assertTrue(receipt["approval"]["approved"])
        self.assertEqual(receipt["approval"]["approved_by"], "governance-owner")
        self.assertFalse(receipt["execution"]["automatic_application_allowed"])
        self.assertFalse(receipt["execution"]["applied"])
        self.assertFalse(receipt["production"]["promotion_allowed"])
        self.assertEqual(len(receipt["source"]["change_request_sha256"]), 64)
        self.assertEqual(len(receipt["receipt_sha256"]), 64)

    def test_rejection_is_recorded_and_does_not_mark_approval(self):
        receipt = self.build_receipt(decision="REJECT")

        self.assertEqual(receipt["decision_status"], "REJECTED")
        self.assertFalse(receipt["approval"]["approved"])
        self.assertIsNone(receipt["approval"]["approved_by"])

    def test_approval_rejects_non_pending_request(self):
        request = self.base_request()
        request["request_status"] = "NO_CHANGE"

        with self.assertRaisesRegex(ValueError, "only pending increase requests"):
            self.build_receipt(request=request)

    def test_contract_and_governance_invariants_are_required(self):
        invalid_contract = self.base_request()
        invalid_contract["contract"] = "unexpected"
        with self.assertRaisesRegex(ValueError, "invalid change request contract"):
            self.build_receipt(request=invalid_contract)

        unsafe_execution = self.base_request()
        unsafe_execution["execution"]["automatic_application_allowed"] = True
        with self.assertRaisesRegex(ValueError, "automatic application must remain disabled"):
            self.build_receipt(request=unsafe_execution)

    def test_actor_and_reason_are_mandatory(self):
        with self.assertRaisesRegex(ValueError, "actor is required"):
            build(
                self.base_request(),
                decision="APPROVE",
                actor=" ",
                reason="valid",
                source_artifact_id="1",
                repository="example/reqsys",
                run_id="2",
            )

        with self.assertRaisesRegex(ValueError, "reason is required"):
            build(
                self.base_request(),
                decision="APPROVE",
                actor="owner",
                reason=" ",
                source_artifact_id="1",
                repository="example/reqsys",
                run_id="2",
            )


if __name__ == "__main__":
    unittest.main()
