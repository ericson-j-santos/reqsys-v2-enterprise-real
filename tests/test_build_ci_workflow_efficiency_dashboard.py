import unittest

from scripts.build_ci_workflow_efficiency_dashboard import build_dashboard, calculate_efficiency_score


class WorkflowEfficiencyDashboardTests(unittest.TestCase):
    def test_calculates_score_from_observed_and_savable_runs(self):
        recommendations = [
            {"pr_presence_count": 4, "potential_runs_saved": 3},
            {"pr_presence_count": 2, "potential_runs_saved": 1},
        ]
        self.assertEqual(calculate_efficiency_score(recommendations), 33.33)

    def test_builds_ranked_dashboard_and_history(self):
        source = {
            "summary": {
                "pr_sample_count": 4,
                "observed_workflow_count": 8,
                "recommended_path_review_count": 2,
            },
            "recommendations": [
                {
                    "workflow": "Runtime Risk Scoring",
                    "pr_presence_count": 4,
                    "pr_presence_percent": 100,
                    "potential_runs_saved": 3,
                    "decision": "RECOMMEND_PATH_REVIEW",
                },
                {
                    "workflow": "PR Quality Review",
                    "pr_presence_count": 2,
                    "pr_presence_percent": 50,
                    "potential_runs_saved": 1,
                    "decision": "KEEP_MEASURING",
                },
            ],
        }

        dashboard, history = build_dashboard(source, {"entries": []})

        self.assertEqual(dashboard["mode"], "report_only")
        self.assertEqual(dashboard["top_workflows"][0]["workflow"], "Runtime Risk Scoring")
        self.assertEqual(dashboard["summary"]["estimated_runs_saved"], 4)
        self.assertFalse("automatic_filtering" in dashboard)
        self.assertEqual(len(history["entries"]), 1)

    def test_preserves_last_thirty_history_entries(self):
        source = {"summary": {}, "recommendations": []}
        previous = {
            "entries": [
                {"generated_at": str(index), "workflow_efficiency_score": 100}
                for index in range(35)
            ]
        }

        _, history = build_dashboard(source, previous)

        self.assertEqual(len(history["entries"]), 30)
        self.assertEqual(history["entries"][-1]["workflow_efficiency_score"], 100.0)

    def test_empty_source_is_non_blocking_and_green(self):
        dashboard, _ = build_dashboard({}, {})

        self.assertFalse(dashboard["source_available"])
        self.assertEqual(dashboard["executive_card"]["score_percent"], 100.0)
        self.assertEqual(dashboard["executive_card"]["recommended_action"], "KEEP_MEASURING")


if __name__ == "__main__":
    unittest.main()
