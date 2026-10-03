import unittest

from scripts.build_ux_remediation_governance_trend import evaluate


def dashboard(sla=95, closure=100, reopen=0, overdue=0, high=12, medium=36):
    return {"cards": [{
        "id": "ux-recovery-standard-gold-readiness",
        "remediation_governance": {
            "within_sla_percent": sla,
            "validated_closure_rate_percent": closure,
            "reopening_count": reopen,
            "overdue_open_count": overdue,
            "mttr_hours_by_severity": {"high": high, "medium": medium},
            "generated_at": "2026-07-15T20:00:00Z",
        },
    }]}


class GovernanceTrendTests(unittest.TestCase):
    def test_stable_when_targets_are_met(self):
        history, report, output = evaluate([], dashboard(), run_id="1", head_sha="abcdef123")
        self.assertEqual(len(history), 1)
        self.assertEqual(report["status"], "UX_REMEDIATION_GOVERNANCE_STABLE")
        self.assertEqual(report["alerts"], [])
        self.assertFalse(report["production_blocker"])
        self.assertEqual(output["cards"][0]["remediation_governance_trend"]["highest_severity"], "none")

    def test_detects_target_breaches(self):
        _, report, _ = evaluate([], dashboard(sla=70, closure=80, reopen=2, overdue=1, high=30, medium=80), run_id="2", head_sha="abcdef456")
        codes = {item["code"] for item in report["alerts"]}
        self.assertIn("sla_below_target", codes)
        self.assertIn("validated_closure_below_target", codes)
        self.assertIn("reopening_above_target", codes)
        self.assertIn("mttr_high_above_target", codes)
        self.assertIn("mttr_medium_above_target", codes)
        self.assertIn("overdue_open_items", codes)
        self.assertEqual(report["highest_severity"], "high")

    def test_detects_deterioration_against_previous_sample(self):
        previous = [{
            "source_run_id": "1",
            "within_sla_percent": 98,
            "validated_closure_rate_percent": 100,
            "reopening_count": 0,
            "overdue_open_count": 0,
            "mttr_high_hours": 10,
            "mttr_medium_hours": 30,
        }]
        _, report, _ = evaluate(previous, dashboard(sla=85, closure=90, reopen=1), run_id="2", head_sha="abcdef789")
        codes = {item["code"] for item in report["alerts"]}
        self.assertIn("sla_deterioration", codes)
        self.assertIn("validated_closure_deterioration", codes)
        self.assertIn("reopening_growth", codes)

    def test_is_idempotent_by_run_id(self):
        previous = [{"source_run_id": "2", "within_sla_percent": 10}]
        history, _, _ = evaluate(previous, dashboard(), run_id="2", head_sha="abcdef999")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["source_head_sha"], "abcdef999")


if __name__ == "__main__":
    unittest.main()
