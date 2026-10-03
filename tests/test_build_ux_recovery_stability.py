import unittest

from scripts.build_ux_recovery_stability import evaluate


class UxRecoveryStabilityTests(unittest.TestCase):
    def test_blocks_with_insufficient_samples(self):
        report = evaluate([
            {"ux_100_ready": True, "recovery_rate": 90, "average_recovery_seconds": 20},
            {"ux_100_ready": True, "recovery_rate": 85, "average_recovery_seconds": 25},
        ])
        self.assertFalse(report["standard_gold_ready"])
        self.assertFalse(report["criteria"]["minimum_samples_met"])

    def test_requires_consecutive_qualified_samples(self):
        report = evaluate([
            {"ux_100_ready": True, "recovery_rate": 90, "average_recovery_seconds": 20},
            {"ux_100_ready": False, "recovery_rate": 40, "average_recovery_seconds": 45},
            {"ux_100_ready": True, "recovery_rate": 80, "average_recovery_seconds": 24},
        ])
        self.assertFalse(report["standard_gold_ready"])
        self.assertEqual(report["consecutive_qualified_samples"], 1)

    def test_approves_stable_multi_sample_evidence(self):
        report = evaluate([
            {"ux_100_ready": False, "recovery_rate": 50, "average_recovery_seconds": 35},
            {"ux_100_ready": True, "recovery_rate": 75, "average_recovery_seconds": 28},
            {"ux_100_ready": True, "recovery_rate": 85, "average_recovery_seconds": 22},
        ])
        self.assertTrue(report["standard_gold_ready"])
        self.assertEqual(report["status"], "UX_STANDARD_GOLD_EVIDENCE_READY")
        self.assertFalse(report["production_blocker"])
        self.assertTrue(report["human_approval_required"])


if __name__ == "__main__":
    unittest.main()
