import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ci_budget_guard.py"
FIXTURE = ROOT / "tests" / "fixtures" / "ci-budget" / "pr-1954-changed-files.txt"


def load_module():
    spec = importlib.util.spec_from_file_location("ci_budget_guard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def test_repository_budget_contract_passes():
    result = MODULE.evaluate_repository(ROOT)
    assert result["status"] == "passed", result["blockers"]
    assert result["blocking_workflow_count"] <= result["blocking_workflow_budget"]
    assert result["blocking_workflow_budget"] == 10
    assert result["protected_workflows_preserved"] is True


def test_pr_1954_fixture_avoids_expensive_specialized_workflows():
    changed = FIXTURE.read_text(encoding="utf-8").splitlines()
    assert MODULE.specialized_candidates(changed) == []


def test_negative_control_blocks_over_budget():
    policy = {
        "blocking_workflow_budget": 2,
        "protected_workflows": ["A", "B", "C"],
        "report_only_workflows": [],
    }
    blockers = MODULE._policy_blockers(policy)
    assert any("budget excedido" in item for item in blockers)


def test_negative_control_blocks_protected_report_only_overlap():
    policy = {
        "blocking_workflow_budget": 10,
        "protected_workflows": ["A", "B"],
        "report_only_workflows": ["B"],
    }
    blockers = MODULE._policy_blockers(policy)
    assert any("report-only" in item for item in blockers)


def test_kindle_physical_jobs_are_fail_closed_for_pull_requests():
    text = (ROOT / ".github" / "workflows" / "kindle-knowledge-local-cache.yml").read_text(
        encoding="utf-8"
    )
    for job in MODULE.KINDLE_PHYSICAL_JOBS:
        block = MODULE._job_block(text, job)
        assert "github.event_name != 'pull_request'" in block, job


def test_ci_budget_guard_is_inside_canonical_ci_not_extra_workflow():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "  ci-budget-guard:" in text
    assert "name: CI Budget Guard" in text
    assert "python scripts/ci_budget_guard.py" in text
    assert text.count("needs: [ci-router, ci-budget-guard]") >= 3
    assert (
        "needs: [ci-router, ci-budget-guard, backend-lint, backend-test, "
        "frontend-build, frontend-e2e-responsive]"
    ) in text


def test_policy_keeps_protected_and_report_only_disjoint():
    policy = json.loads(
        (ROOT / "config" / "ci-workflow-pareto-policy.json").read_text(encoding="utf-8")
    )
    assert set(policy["protected_workflows"]).isdisjoint(policy["report_only_workflows"])


def test_governed_merge_queue_delegates_frontend_validation_to_required_ci():
    workflow = (
        ROOT / ".github" / "workflows" / "governed-merge-queue.yml"
    ).read_text(encoding="utf-8")
    policy = json.loads(
        (
            ROOT / "governance" / "merge" / "current-sha-required-workflows.json"
        ).read_text(encoding="utf-8")
    )
    required = set(policy["required_workflows"])

    assert {"CI — ReqSys v2 Enterprise", "CI Enterprise Fast"} <= required
    assert "actions/setup-node@" not in workflow
    assert "npm ci" not in workflow
    assert "npm run lint" not in workflow
    assert "npm run typecheck" not in workflow
    assert (
        "needs: [resolve-context, sdd-contract, isolated-validation, "
        "temporary-integration, current-sha-stability]"
    ) in workflow
