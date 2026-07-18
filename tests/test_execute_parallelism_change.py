import hashlib
import json
import unittest

from scripts.execute_parallelism_change import build_execution


def canonical(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class GovernedParallelismExecutorTests(unittest.TestCase):
    def receipt(self):
        payload = {
            "schema_version": "1.0.0",
            "contract": "reqsys-parallelism-approval-receipt",
            "decision_status": "APPROVED",
            "approval": {"approved": True},
            "execution": {"automatic_application_allowed": False},
            "production": {"promotion_allowed": False},
            "change": {"current_stage": 1, "recommended_stage": 2},
        }
        payload["receipt_sha256"] = hashlib.sha256(canonical(payload)).hexdigest()
        return payload

    def metrics(self):
        return {
            "contract": "reqsys-parallelism-effect-index",
            "stable": True,
            "stable_windows": 3,
            "error_rate": 0.01,
            "max_error_rate": 0.02,
        }

    def test_apply_one_stage_in_dev(self):
        result = build_execution(
            self.receipt(), self.metrics(), environment="dev", action="APPLY", actor="ops-owner"
        )
        self.assertEqual(result["status"], "APPLIED")
        self.assertEqual(result["change"]["target_stage"], 2)
        self.assertEqual(result["change"]["delta"], 1)
        self.assertFalse(result["guardrails"]["production_promotion_allowed"])

    def test_rollback_returns_to_previous_stage(self):
        result = build_execution(
            self.receipt(), self.metrics(), environment="stg", action="ROLLBACK", actor="ops-owner"
        )
        self.assertEqual(result["status"], "ROLLED_BACK")
        self.assertEqual(result["change"]["target_stage"], 1)
        self.assertEqual(result["change"]["delta"], -1)

    def test_production_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "production"):
            build_execution(
                self.receipt(), self.metrics(), environment="prod", action="APPLY", actor="ops-owner"
            )

    def test_tampered_receipt_is_blocked(self):
        receipt = self.receipt()
        receipt["change"]["recommended_stage"] = 3
        with self.assertRaisesRegex(ValueError, "checksum"):
            build_execution(receipt, self.metrics(), environment="dev", action="APPLY", actor="ops-owner")

    def test_more_than_one_stage_is_blocked(self):
        receipt = self.receipt()
        receipt["change"]["recommended_stage"] = 3
        unsigned = dict(receipt)
        unsigned.pop("receipt_sha256")
        receipt["receipt_sha256"] = hashlib.sha256(canonical(unsigned)).hexdigest()
        with self.assertRaisesRegex(ValueError, "one-stage"):
            build_execution(receipt, self.metrics(), environment="dev", action="APPLY", actor="ops-owner")

    def test_unstable_metrics_are_blocked(self):
        metrics = self.metrics()
        metrics["stable"] = False
        with self.assertRaisesRegex(ValueError, "unstable"):
            build_execution(self.receipt(), metrics, environment="dev", action="APPLY", actor="ops-owner")


if __name__ == "__main__":
    unittest.main()
