import unittest

from scripts.enrich_reqsys_state_workflow_efficiency import build_card, enrich_runtime_index, enrich_state


class WorkflowEfficiencyStateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.efficiency = {
            "mode": "report_only",
            "executive_card": {
                "title": "Workflow Efficiency",
                "status": "green",
                "score_percent": 87.5,
                "trend_delta_points": 4.0,
                "recommended_action": "REVIEW_TOP_WORKFLOW",
            },
            "summary": {"pr_sample_count": 8, "estimated_runs_saved": 12},
            "top_workflows": [{"workflow": "Runtime Risk Scoring"}],
        }

    def test_builds_executive_card(self):
        card = build_card(self.efficiency)
        self.assertEqual(card["score_percent"], 87.5)
        self.assertEqual(card["top_workflow"], "Runtime Risk Scoring")
        self.assertEqual(card["mode"], "report_only")

    def test_enriches_runtime_index_idempotently(self):
        index = {"schema_version": "1.3.0", "cards": {}, "summary": {}, "links": {}, "guardrails": []}
        first = enrich_runtime_index(index, self.efficiency)
        second = enrich_runtime_index(first, self.efficiency)

        self.assertEqual(second["schema_version"], "1.4.0")
        self.assertEqual(second["cards"]["workflow_efficiency"]["score_percent"], 87.5)
        self.assertEqual(second["links"]["workflow_efficiency"], "data/ci-workflow-efficiency-dashboard.json")
        self.assertEqual(second["guardrails"].count("workflow_efficiency_is_report_only"), 1)

    def test_enriches_main_operational_state(self):
        state = {"contract": "main-operational-state-snapshot", "indicators": {}}
        enriched = enrich_state(state, self.efficiency)

        self.assertEqual(enriched["workflow_efficiency_score"], 87.5)
        self.assertEqual(enriched["workflow_efficiency_status"], "green")
        self.assertEqual(enriched["indicators"]["workflow_efficiency"]["estimated_runs_saved"], 12)


if __name__ == "__main__":
    unittest.main()
