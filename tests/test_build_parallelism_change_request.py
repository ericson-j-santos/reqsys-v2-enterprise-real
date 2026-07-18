import unittest

from scripts.build_parallelism_change_request import build


class ParallelismChangeRequestTests(unittest.TestCase):
    def base_policy(self):
        return {
            "contract": "reqsys-staged-parallelism-policy",
            "source_of_truth": "reqsys-parallelism-effect-index",
            "decision": "KEEP_LIMITS",
            "reason": "test",
            "current_stage": 1,
            "recommended_stage": 1,
            "rollback_on_instability": True,
        }

    def test_increase_requires_human_approval(self):
        policy = self.base_policy()
        policy.update(decision="INCREASE_ONE_STAGE", recommended_stage=2)
        result = build(policy)
        self.assertEqual(result["request_status"], "AWAITING_HUMAN_APPROVAL")
        self.assertFalse(result["approval"]["approved"])
        self.assertFalse(result["execution"]["automatic_application_allowed"])
        self.assertFalse(result["production"]["promotion_allowed"])

    def test_instability_recommends_rollback(self):
        policy = self.base_policy()
        policy.update(current_stage=2, recommended_stage=1)
        result = build(policy)
        self.assertEqual(result["request_status"], "ROLLBACK_RECOMMENDED")
        self.assertTrue(result["rollback"]["recommended"])

    def test_no_change_is_explicit(self):
        result = build(self.base_policy())
        self.assertEqual(result["request_status"], "NO_CHANGE")
        self.assertEqual(result["change_type"], "KEEP_LIMITS")


if __name__ == "__main__":
    unittest.main()
