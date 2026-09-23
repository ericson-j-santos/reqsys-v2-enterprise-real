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

    def test_fast_classifier_is_manual_only_after_canonical_router(self):
        text = (WORKFLOWS / "pr-fast-classifier.yml").read_text(encoding="utf-8")
        trigger = text.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger)
        self.assertNotIn("pull_request:", trigger)

    def test_preview_contract_is_manual_only_after_canonical_router(self):
        text = (WORKFLOWS / "preview-environment-contract.yml").read_text(encoding="utf-8")
        trigger = text.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger)
        self.assertNotIn("pull_request:", trigger)

    def test_advisory_risk_quality_and_predictive_leave_pr_critical_path(self):
        for workflow in (
            "runtime-risk-scoring.yml",
            "pr-quality-review.yml",
            "predictive-regression-guard.yml",
        ):
            text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
            trigger = text.split("permissions:", 1)[0]
            self.assertIn("workflow_dispatch:", trigger, workflow)
            self.assertNotIn("pull_request:", trigger, workflow)

    def test_router_contract_moves_advisory_workflows_post_ci(self):
        router = load_router()
        self.assertIn(
            ".github/workflows/runtime-risk-scoring.yml",
            router.MANUAL_ONLY_ADVISORY,
        )
        self.assertEqual(
            router.POST_CI_ROUTER,
            ".github/workflows/ci-advisory-router.yml",
        )
        advisory = (WORKFLOWS / "ci-advisory-router.yml").read_text(encoding="utf-8")
        trigger = advisory.split("permissions:", 1)[0]
        self.assertIn("workflow_run:", trigger)
        self.assertIn("CI — ReqSys v2 Enterprise", trigger)
        self.assertIn("types: [completed]", trigger)
        self.assertIn("automatic_dispatch: false", advisory)
        self.assertIn("critical_path_blocker: false", advisory)
        self.assertNotIn("actions: write", advisory)

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

    def test_domain_specific_gates_are_path_scoped_on_pull_request(self):
        expectations = {
            "bacen-production-formal-gate.yml": (
                '"governance/bacen/BACEN-CONTROL-MATRIX.yaml"',
                '"scripts/validate_bacen_production_gate.py"',
            ),
            "enterprise-runtime-governance-gates.yml": (
                '"backend/**"',
                '"infra/**"',
                '"scripts/governance/enterprise_runtime_governance_gates.py"',
            ),
            "disposable-probe-base-guard.yml": (
                '".github/workflows/**"',
                '"scripts/validate_disposable_probe_base.py"',
            ),
            "minimum-controlled-version-gate.yml": (
                '"governance/minimum-controlled-version.json"',
                '"scripts/validate_minimum_controlled_version.py"',
            ),
        }
        for workflow, tokens in expectations.items():
            text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
            trigger = text.split("permissions:", 1)[0]
            self.assertIn("pull_request:", trigger)
            self.assertIn("paths:", trigger)
            for token in tokens:
                self.assertIn(token, trigger, workflow)

    def test_pr_governed_ci_does_not_rerun_on_label_change(self):
        text = (WORKFLOWS / "pr-governed-ci-validation.yml").read_text(encoding="utf-8")
        trigger = text.split("permissions:", 1)[0]
        self.assertIn("opened, synchronize, reopened, ready_for_review", trigger)
        self.assertNotIn("labeled", trigger)

    def test_test_quality_gate_avoids_global_workflow_wildcard(self):
        text = (WORKFLOWS / "test-quality-gate.yml").read_text(encoding="utf-8")
        trigger = text.split("pull_request:", 1)[1].split("push:", 1)[0]
        self.assertNotIn('".github/workflows/**"', trigger)
        for expected in (
            '".github/workflows/test-quality-gate.yml"',
            '".github/workflows/ci.yml"',
            '".github/workflows/ci-enterprise-fast.yml"',
            '".github/workflows/ci-e2e-governado.yml"',
        ):
            self.assertIn(expected, trigger)

    def test_pr_governed_ci_is_path_scoped_to_ci_contract(self):
        text = (WORKFLOWS / "pr-governed-ci-validation.yml").read_text(encoding="utf-8")
        trigger = text.split("permissions:", 1)[0]
        self.assertIn("paths:", trigger)
        for expected in (
            '".github/workflows/ci.yml"',
            '".github/workflows/ci-security.yml"',
            '".github/workflows/ci-e2e-governado.yml"',
            '"scripts/select_backend_tests.py"',
        ):
            self.assertIn(expected, trigger)

    def test_requirement_lifecycle_does_not_rerun_on_synchronize(self):
        text = (WORKFLOWS / "requirement-lifecycle-evidence.yml").read_text(encoding="utf-8")
        trigger = text.split("permissions:", 1)[0]
        self.assertIn("opened, reopened, closed", trigger)
        self.assertNotIn("synchronize", trigger)

    def test_pre_pr_push_and_pull_request_share_concurrency_group(self):
        text = (WORKFLOWS / "pre-pr-readiness.yml").read_text(encoding="utf-8")
        self.assertIn(
            "pre-pr-readiness-${{ github.event.pull_request.head.ref || github.ref_name }}",
            text,
        )
        self.assertIn("cancel-in-progress: true", text)

    def test_deep_governance_review_only_materializes_on_label(self):
        text = (WORKFLOWS / "deep-governance-review.yml").read_text(encoding="utf-8")
        trigger = text.split("permissions:", 1)[0]
        self.assertIn("types: [labeled]", trigger)
        self.assertNotIn("synchronize", trigger)

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
