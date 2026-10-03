import unittest

from scripts.consolidate_user_experience_public_availability import consolidate


class ConsolidatePublicAvailabilityTests(unittest.TestCase):
    def healthy(self):
        return {
            "environments": {
                "dev": {"pass_rate": 100.0},
                "stg": {"pass_rate": 100.0},
                "prod": {"pass_rate": 100.0},
            },
            "sample_count": 3,
            "stable_sequence": 3,
            "common_fingerprint": "abc",
            "drift_detected": False,
            "degradation_detected": False,
        }

    def test_eligible_only_with_complete_stable_evidence(self):
        state, brief = consolidate(self.healthy(), {"readiness": "ready"}, {"production_ready": False})
        card = state["cards"]["user_experience_public_availability"]
        self.assertEqual(card["status"], "PUBLIC_AVAILABILITY_STABLE")
        self.assertTrue(card["human_review_eligible"])
        self.assertEqual(state["readiness"], "ready")
        self.assertFalse(brief["production_ready"])

    def test_drift_forces_review(self):
        evidence = self.healthy()
        evidence["drift_detected"] = True
        state, _ = consolidate(evidence, {}, {})
        card = state["cards"]["user_experience_public_availability"]
        self.assertEqual(card["status"], "PUBLIC_AVAILABILITY_REVIEW")
        self.assertFalse(card["human_review_eligible"])

    def test_incomplete_coverage_forces_review(self):
        evidence = self.healthy()
        evidence["environments"].pop("prod")
        state, _ = consolidate(evidence, {}, {})
        self.assertFalse(state["cards"]["user_experience_public_availability"]["coverage_complete"])

    def test_idempotent(self):
        evidence = self.healthy()
        state1, brief1 = consolidate(evidence, {}, {})
        state2, brief2 = consolidate(evidence, state1, brief1)
        self.assertEqual(state1, state2)
        self.assertEqual(brief1, brief2)


if __name__ == "__main__":
    unittest.main()
