import hashlib
import json
import unittest

from scripts.apply_parallelism_target_adapter import apply_adapter, canonical


class ParallelismTargetAdapterTests(unittest.TestCase):
    def state(self, target="worker", environment="dev"):
        return {
            "contract": "reqsys-parallelism-target-state",
            "schema_version": "1.0.0",
            "target": target,
            "environment": environment,
            "stage": 1,
            "version": 7,
            "validation_pending": False,
            "applied_execution_receipts": [],
        }

    def execution(self, environment="dev", target_stage=2):
        payload = {
            "schema_version": "1.0.0",
            "contract": "reqsys-parallelism-execution-receipt",
            "environment": environment,
            "status": "APPLIED",
            "change": {"previous_stage": 1, "target_stage": target_stage, "delta": target_stage - 1},
            "guardrails": {
                "non_production_only": True,
                "production_promotion_allowed": False,
            },
        }
        payload["execution_sha256"] = hashlib.sha256(canonical(payload)).hexdigest()
        return payload

    def apply(self, state=None, execution=None, **kwargs):
        return apply_adapter(
            state or self.state(),
            execution or self.execution(),
            target=kwargs.get("target", "worker"),
            environment=kwargs.get("environment", "dev"),
            expected_version=kwargs.get("expected_version", 7),
            smoke_healthy=kwargs.get("smoke_healthy", True),
            actor="ops-owner",
        )

    def test_applies_with_compare_and_swap_and_smoke(self):
        result = self.apply()
        self.assertEqual(result.receipt["status"], "APPLIED")
        self.assertEqual(result.state["stage"], 2)
        self.assertEqual(result.state["version"], 8)
        self.assertFalse(result.state["validation_pending"])
        self.assertEqual(len(result.receipt["receipt_sha256"]), 64)

    def test_is_idempotent_for_same_execution_receipt(self):
        execution = self.execution()
        state = self.state()
        state["applied_execution_receipts"] = [execution["execution_sha256"]]
        result = self.apply(state=state, execution=execution)
        self.assertEqual(result.receipt["status"], "IDEMPOTENT_NOOP")
        self.assertEqual(result.state["version"], 7)

    def test_compare_and_swap_rejects_stale_version(self):
        with self.assertRaisesRegex(ValueError, "compare-and-swap"):
            self.apply(expected_version=6)

    def test_pending_validation_blocks_new_execution(self):
        state = self.state()
        state["validation_pending"] = True
        with self.assertRaisesRegex(ValueError, "pending validation"):
            self.apply(state=state)

    def test_failed_smoke_rolls_back_effectively(self):
        result = self.apply(smoke_healthy=False)
        self.assertEqual(result.receipt["status"], "ROLLED_BACK")
        self.assertEqual(result.state["stage"], 1)
        self.assertEqual(result.state["version"], 9)
        self.assertTrue(result.receipt["rollback"]["executed"])

    def test_production_and_large_delta_are_blocked(self):
        with self.assertRaisesRegex(ValueError, "production"):
            apply_adapter(
                self.state(environment="prod"),
                self.execution(environment="prod"),
                target="worker",
                environment="prod",
                expected_version=7,
                smoke_healthy=True,
                actor="ops-owner",
            )
        with self.assertRaisesRegex(ValueError, "exceeds one stage"):
            self.apply(execution=self.execution(target_stage=3))

    def test_all_governed_targets_are_supported(self):
        for target in ("worker", "queue", "api"):
            with self.subTest(target=target):
                result = self.apply(state=self.state(target=target), target=target)
                self.assertEqual(result.receipt["target"], target)


if __name__ == "__main__":
    unittest.main()
