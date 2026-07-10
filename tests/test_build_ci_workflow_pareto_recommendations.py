import unittest

from scripts.build_ci_workflow_pareto_recommendations import build_recommendations


class WorkflowParetoRecommendationsTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "minimum_pr_sample": 3,
            "minimum_presence_percent": 50,
            "minimum_potential_runs_saved": 2,
            "target_average_workflows_per_pr": 10,
            "protected_workflows": ["ReqSys Required Fast Gate"],
            "report_only_workflows": ["Runtime Risk Scoring", "PR Quality Review"],
        }

    def test_recommends_high_volume_report_only_workflow(self):
        metrics = {
            "pull_requests": [
                {"pr_number": 3, "workflows": ["ReqSys Required Fast Gate", "Runtime Risk Scoring"]},
                {"pr_number": 2, "workflows": ["ReqSys Required Fast Gate", "Runtime Risk Scoring"]},
                {"pr_number": 1, "workflows": ["ReqSys Required Fast Gate", "Runtime Risk Scoring"]},
            ]
        }

        payload = build_recommendations(metrics, self.policy)

        self.assertEqual(payload["summary"]["decision"], "REVIEW_RECOMMENDED")
        self.assertEqual(payload["summary"]["recommended_path_review_count"], 1)
        recommendation = payload["recommendations"][0]
        self.assertEqual(recommendation["workflow"], "Runtime Risk Scoring")
        self.assertEqual(recommendation["decision"], "RECOMMEND_PATH_REVIEW")
        self.assertFalse(recommendation["automatic_change_allowed"])

    def test_never_recommends_protected_workflow(self):
        metrics = {
            "pull_requests": [
                {"pr_number": 3, "workflows": ["ReqSys Required Fast Gate"]},
                {"pr_number": 2, "workflows": ["ReqSys Required Fast Gate"]},
                {"pr_number": 1, "workflows": ["ReqSys Required Fast Gate"]},
            ]
        }

        payload = build_recommendations(metrics, self.policy)

        self.assertEqual(payload["recommendations"], [])
        self.assertEqual(payload["protected_workflows_observed"][0]["decision"], "PROTECTED_REQUIRED_GATE")

    def test_keeps_measuring_when_sample_is_small(self):
        metrics = {
            "pull_requests": [
                {"pr_number": 2, "workflows": ["PR Quality Review"]},
                {"pr_number": 1, "workflows": ["PR Quality Review"]},
            ]
        }

        payload = build_recommendations(metrics, self.policy)

        self.assertEqual(payload["summary"]["decision"], "KEEP_MEASURING")
        self.assertEqual(payload["recommendations"][0]["decision"], "KEEP_MEASURING")


if __name__ == "__main__":
    unittest.main()
