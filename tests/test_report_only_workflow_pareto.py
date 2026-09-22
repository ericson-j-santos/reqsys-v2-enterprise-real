import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
POLICY = ROOT / "config" / "ci-workflow-pareto-policy.json"


class ReportOnlyWorkflowParetoTest(unittest.TestCase):
    def test_scope_labeler_only_materializes_on_pr_open(self):
        text = (WORKFLOWS / "pr-scope-labeler.yml").read_text(encoding="utf-8")
        trigger = text.split("permissions:", 1)[0]
        self.assertIn("pull_request:", trigger)
        self.assertIn("- opened", trigger)
        self.assertNotIn("- synchronize", trigger)
        self.assertNotIn("- reopened", trigger)
        self.assertNotIn("- ready_for_review", trigger)

    def test_fast_classifier_does_not_rerun_for_label_only_changes(self):
        text = (WORKFLOWS / "pr-fast-classifier.yml").read_text(encoding="utf-8")
        trigger = text.split("permissions:", 1)[0]
        self.assertIn("opened, synchronize, reopened, ready_for_review", trigger)
        self.assertNotIn("labeled", trigger)
        self.assertNotIn("unlabeled", trigger)

    def test_preview_contract_is_path_scoped_to_runtime_surface(self):
        text = (WORKFLOWS / "preview-environment-contract.yml").read_text(encoding="utf-8")
        trigger = text.split("workflow_dispatch:", 1)[0]
        self.assertIn("paths:", trigger)
        for expected in (
            '"backend/**"',
            '"frontend/**"',
            '"runtime/**"',
            '"services/**"',
            '"infra/**"',
            '".github/workflows/preview-environment-contract.yml"',
        ):
            self.assertIn(expected, trigger)

    def test_optimized_workflows_are_report_only_not_protected(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        optimized = {
            "Preview Environment Contract",
            "PR Scope Labeler",
            "PR Fast Classifier",
        }
        self.assertTrue(optimized.issubset(set(policy["report_only_workflows"])))
        self.assertTrue(optimized.isdisjoint(set(policy["protected_workflows"])))


if __name__ == "__main__":
    unittest.main()
