import unittest

from scripts.build_executive_promotion_advisor import build


class ExecutivePromotionAdvisorTests(unittest.TestCase):
    def green_inputs(self):
        return (
            {"summary": {"status": "green", "production_ready": True}},
            {"executive_readiness": {"ready_for_production": True, "blockers": []}},
            {"overall": {"state": "green"}, "totals": {"severity": {"critical": 0, "high": 0}}},
            {"mergeable": True},
            {"summary": {"latest_decision": "HOMOLOGATED", "latest_status": "passed"}},
        )

    def test_ready(self):
        payload = build(*self.green_inputs(), "ready-1")
        self.assertEqual(payload["decision"], "READY")
        self.assertEqual(payload["confidence_percent"], 100.0)
        self.assertFalse(payload["production_blocker"])
        self.assertTrue(payload["human_approval_required"])

    def test_review_when_evidence_is_unknown(self):
        runtime, readiness, security, merge, _ = self.green_inputs()
        payload = build(runtime, readiness, security, merge, {}, "review-1")
        self.assertEqual(payload["decision"], "REVIEW")
        self.assertIn("workflow_efficiency", payload["risk_domains"])
        self.assertFalse(payload["production_blocker"])

    def test_hold_when_security_blocks(self):
        runtime, readiness, security, merge, history = self.green_inputs()
        security["overall"]["production_blocked"] = True
        payload = build(runtime, readiness, security, merge, history, "hold-1")
        self.assertEqual(payload["decision"], "HOLD")
        self.assertEqual(payload["inputs"]["security"], "red")
        self.assertFalse(payload["production_blocker"])

    def test_hold_when_readiness_has_blockers(self):
        runtime, readiness, security, merge, history = self.green_inputs()
        readiness["executive_readiness"]["blockers"] = ["runtime"]
        payload = build(runtime, readiness, security, merge, history, "hold-2")
        self.assertEqual(payload["decision"], "HOLD")

    def test_deterministic_except_timestamp(self):
        inputs = self.green_inputs()
        first = build(*inputs, "same")
        second = build(*inputs, "same")
        first.pop("generated_at")
        second.pop("generated_at")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
