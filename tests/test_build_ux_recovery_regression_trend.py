import unittest

from scripts.build_ux_recovery_regression_trend import evaluate


def dashboard(confidence=90, rate=80, seconds=20, sequence=3, ready=True):
    return {"cards": [{
        "id": "ux-recovery-standard-gold-readiness",
        "confidence_percent": confidence,
        "recovery_rate_average": rate,
        "recovery_seconds_average": seconds,
        "consecutive_qualified_samples": sequence,
        "standard_gold_ready": ready,
        "generated_at": "2026-07-15T18:00:00Z",
    }]}


class UxRecoveryRegressionTrendTests(unittest.TestCase):
    def test_first_sample_is_stable(self):
        history, report = evaluate([], dashboard(), run_id="1", head_sha="abcdef123")
        self.assertEqual(len(history), 1)
        self.assertFalse(report["regression_detected"])
        self.assertEqual(report["status"], "UX_RECOVERY_TREND_STABLE")

    def test_detects_all_regression_signals(self):
        previous = [{
            "source_run_id": "1",
            "confidence_percent": 95,
            "recovery_rate_average": 90,
            "recovery_seconds_average": 18,
            "consecutive_qualified_samples": 4,
        }]
        _, report = evaluate(previous, dashboard(70, 80, 30, 1, False), run_id="2", head_sha="abcdef456")
        self.assertTrue(report["regression_detected"])
        self.assertEqual(set(report["alerts"]), {
            "recovery_rate_drop", "recovery_time_increase", "qualified_sequence_break", "confidence_drop"
        })
        self.assertFalse(report["production_blocker"])

    def test_small_variation_does_not_alert(self):
        previous = [{
            "source_run_id": "1",
            "confidence_percent": 90,
            "recovery_rate_average": 80,
            "recovery_seconds_average": 20,
            "consecutive_qualified_samples": 2,
        }]
        _, report = evaluate(previous, dashboard(85, 76, 24, 2), run_id="2", head_sha="abcdef456")
        self.assertFalse(report["regression_detected"])

    def test_is_idempotent_by_run_id(self):
        previous = [{"source_run_id": "2", "confidence_percent": 10}]
        history, _ = evaluate(previous, dashboard(), run_id="2", head_sha="abcdef456")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["confidence_percent"], 90)


if __name__ == "__main__":
    unittest.main()
