import unittest

from scripts.evaluate_parallelism_policy import evaluate


class ParallelismPolicyTests(unittest.TestCase):
    def stable(self):
        return {
            "parallelism_decision": "INCREASE_SAFE",
            "status": "STABLE",
            "risk": "low",
        }

    def unstable(self):
        return {
            "parallelism_decision": "KEEP_LIMITS",
            "status": "OBSERVATION_REQUIRED",
            "risk": "moderate",
        }

    def test_increases_only_one_stage_after_three_stable_windows(self):
        result = evaluate([self.stable(), self.stable(), self.stable()], 1)
        self.assertEqual(result["decision"], "INCREASE_ONE_STAGE")
        self.assertEqual(result["recommended_stage"], 2)
        self.assertFalse(result["automatic_application_allowed"])

    def test_keeps_limits_without_full_stability_window(self):
        result = evaluate([self.stable(), self.stable()], 1)
        self.assertEqual(result["decision"], "KEEP_LIMITS")
        self.assertEqual(result["recommended_stage"], 1)

    def test_rolls_back_one_stage_on_instability(self):
        result = evaluate([self.stable(), self.stable(), self.unstable()], 2)
        self.assertEqual(result["decision"], "KEEP_LIMITS")
        self.assertEqual(result["recommended_stage"], 1)
        self.assertTrue(result["rollback_on_instability"])

    def test_never_exceeds_maximum_stage(self):
        result = evaluate([self.stable(), self.stable(), self.stable()], 3)
        self.assertEqual(result["decision"], "KEEP_LIMITS")
        self.assertEqual(result["recommended_stage"], 3)


if __name__ == "__main__":
    unittest.main()
