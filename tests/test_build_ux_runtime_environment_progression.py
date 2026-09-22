import unittest

from scripts.build_ux_runtime_environment_progression import CARD_ID, build_progression, publish_dashboard


class RuntimeEnvironmentProgressionTests(unittest.TestCase):
    def _sample(self, environment, ready=True, rate=80, seconds=20):
        return {
            "evidence_source": "runtime",
            "verification_status": "verified",
            "environment": environment,
            "ux_100_ready": ready,
            "recovery_rate": rate,
            "average_recovery_seconds": seconds,
        }

    def test_requires_sequential_environment_readiness(self):
        history = [self._sample("stg") for _ in range(3)]
        report = build_progression(history)
        self.assertEqual(report["environments"]["dev"]["status"], "NO_RUNTIME_EVIDENCE")
        self.assertEqual(report["environments"]["stg"]["status"], "WAITING_PREVIOUS_ENVIRONMENT")
        self.assertFalse(report["environments"]["stg"]["eligible_for_human_review"])
        self.assertFalse(report["automatic_promotion"])

    def test_marks_all_environments_ready_only_with_sufficient_verified_runtime_samples(self):
        history = []
        for environment in ("dev", "stg", "prod"):
            history.extend([self._sample(environment) for _ in range(3)])
        report = build_progression(history)
        for environment in ("dev", "stg", "prod"):
            self.assertEqual(report["environments"][environment]["status"], "READY_FOR_HUMAN_REVIEW")
            self.assertTrue(report["environments"][environment]["eligible_for_human_review"])
        self.assertTrue(report["human_approval_required"])
        self.assertFalse(report["production_blocker"])

    def test_ignores_unverified_evidence_and_publishes_idempotent_card(self):
        history = [{"evidence_source": "unverified", "environment": "dev"}]
        card = build_progression(history)
        dashboard = publish_dashboard({"cards": [{"id": CARD_ID}, {"id": "other"}]}, card)
        self.assertEqual(sum(1 for item in dashboard["cards"] if item.get("id") == CARD_ID), 1)
        self.assertEqual(card["environments"]["dev"]["samples"], 0)


if __name__ == "__main__":
    unittest.main()
