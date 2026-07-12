import unittest

from scripts.build_workflow_efficiency_homologation_history import build_history
from scripts.enrich_workflow_efficiency_homologation_trend import (
    enrich_brief,
    enrich_readiness,
    enrich_runtime,
    summarize,
)


class WorkflowEfficiencyHomologationHistoryTests(unittest.TestCase):
    def evidence(self, correlation_id: str, score: float, passed: bool = True):
        return {
            "status": "passed" if passed else "failed",
            "decision": "HOMOLOGATED" if passed else "BLOCKED",
            "correlation_id": correlation_id,
            "generated_at": "2026-07-10T00:00:00+00:00",
            "workflow_efficiency": {
                "score_percent": score,
                "mode": "report-only",
            },
            "errors": [] if passed else ["error"],
        }

    def test_builds_idempotent_history_and_trend(self):
        history = build_history({}, self.evidence("a", 90.0))
        history = build_history(history, self.evidence("b", 92.5))
        history = build_history(history, self.evidence("b", 92.5))

        self.assertEqual(history["summary"]["sample_count"], 2)
        self.assertEqual(history["summary"]["stable_streak"], 2)
        self.assertEqual(history["summary"]["trend"], "up")
        self.assertEqual(history["summary"]["trend_delta_points"], 2.5)
        self.assertFalse(history["summary"]["production_blocker"])

    def test_failed_latest_sample_breaks_streak_without_blocking(self):
        history = build_history({}, self.evidence("a", 90.0))
        history = build_history(history, self.evidence("b", 89.0, passed=False))

        self.assertEqual(history["summary"]["stable_streak"], 0)
        self.assertEqual(history["summary"]["pass_rate_percent"], 50.0)
        self.assertFalse(history["summary"]["eligible_for_blocking_review"])
        self.assertFalse(history["summary"]["production_blocker"])

    def test_eligibility_requires_full_policy(self):
        history = {}
        for index in range(30):
            history = build_history(history, self.evidence(str(index), 95.0 + index / 100))
        self.assertTrue(history["summary"]["eligible_for_blocking_review"])

    def test_enriches_contracts_without_changing_production_decision(self):
        history = build_history({}, self.evidence("a", 93.0))
        trend = summarize(history)

        runtime = enrich_runtime({"summary": {"production_ready": True}}, trend)
        brief = enrich_brief({"estado_producao": "ready"}, trend)
        readiness = enrich_readiness(
            {"executive_readiness": {"decision": "READY_FOR_PRODUCTION", "blockers": []}},
            trend,
        )

        self.assertTrue(runtime["summary"]["production_ready"])
        self.assertEqual(brief["estado_producao"], "ready")
        self.assertEqual(readiness["executive_readiness"]["decision"], "READY_FOR_PRODUCTION")
        self.assertEqual(readiness["executive_readiness"]["blockers"], [])
        domain = readiness["domains"]["workflow_efficiency_homologation_trend"]
        self.assertFalse(domain["production_blocker"])
        self.assertTrue(domain["report_only"])


if __name__ == "__main__":
    unittest.main()
