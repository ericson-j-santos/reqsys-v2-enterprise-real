import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
POLICY = ROOT / "config" / "ci-workflow-pareto-policy.json"
ROUTER = ROOT / "scripts" / "validate_path_based_workflow_router.py"


def load_router():
    spec = importlib.util.spec_from_file_location("validate_path_based_workflow_router", ROUTER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def test_advisory_risk_quality_and_predictive_skip_non_executable_prs(self):
        for workflow in (
            "runtime-risk-scoring.yml",
            "pr-quality-review.yml",
            "predictive-regression-guard.yml",
        ):
            text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
            trigger = text.split("permissions:", 1)[0]
            self.assertIn('"backend/**"', trigger)
            self.assertIn('"frontend/**"', trigger)
            self.assertIn('"runtime/**"', trigger)
            self.assertIn('"services/**"', trigger)
            self.assertNotIn('".github/workflows/**"', trigger)
            self.assertNotIn('"docs/ci/**"', trigger)
            self.assertNotIn('"docs/adr/**"', trigger)
            self.assertNotIn('"tests/**"', trigger)

    def test_router_contract_rejects_broad_advisory_paths(self):
        router = load_router()
        self.assertIn(
            '".github/workflows/**"',
            router.FORBIDDEN_ADVISORY_ROUTING_TOKENS[
                ".github/workflows/runtime-risk-scoring.yml"
            ],
        )
        self.assertIn(
            '"tests/**"',
            router.FORBIDDEN_ADVISORY_ROUTING_TOKENS[
                ".github/workflows/pr-quality-review.yml"
            ],
        )
        self.assertIn(
            '"docs/ops-dashboard/**"',
            router.FORBIDDEN_ADVISORY_ROUTING_TOKENS[
                ".github/workflows/predictive-regression-guard.yml"
            ],
        )
        for workflow, tokens in router.REQUIRED_ROUTING.items():
            self.assertIn('"runtime/**"', tokens, workflow)
            self.assertIn('"services/**"', tokens, workflow)

    def test_pr_ci_watch_uses_only_canonical_completion_signals(self):
        text = (WORKFLOWS / "pr-ci-watch.yml").read_text(encoding="utf-8")
        trigger = text.split("permissions: {}", 1)[0]
        self.assertIn("- CI Enterprise Fast", trigger)
        self.assertIn("- CI — ReqSys v2 Enterprise", trigger)
        for redundant in (
            "Governance Quality Gates",
            "Governança Padrão Ouro",
            "PR Conflict Guard",
            "Branch Protection Audit",
            "Governed Merge Queue",
        ):
            self.assertNotIn(redundant, trigger)
        self.assertIn("github.event.workflow_run.pull_requests[0].number", text)
        self.assertIn("cancel-in-progress: true", text)

    def test_optimized_workflows_are_report_only_not_protected(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        optimized = {
            "Runtime Risk Scoring",
            "PR Quality Review",
            "Predictive Regression Guard",
            "Preview Environment Contract",
            "PR Scope Labeler",
            "PR Fast Classifier",
        }
        self.assertTrue(optimized.issubset(set(policy["report_only_workflows"])))
        self.assertTrue(optimized.isdisjoint(set(policy["protected_workflows"])))


if __name__ == "__main__":
    unittest.main()
