"""Contrato do inventário de required checks versus workflows reais."""
from pathlib import Path

import pytest

from scripts.build_required_checks_stale_inventory import (
    DEFAULT_POLICY,
    DEFAULT_WORKFLOW_DIR,
    build_report,
    build_workflow_inventory,
    load_json,
    normalize,
)

WORKFLOWS = {
    "fast-gate.yml": """
name: ReqSys Required Fast Gate
on:
  pull_request:
    branches: [main]
jobs:
  required-fast-gate:
    name: Required Fast Gate
    runs-on: ubuntu-latest
    steps: [{run: echo ok}]
""",
    "ci.yml": """
name: CI Enterprise
on:
  pull_request:
jobs:
  router:
    name: CI Router
    runs-on: ubuntu-latest
    steps: [{run: echo ok}]
  result:
    name: CI Result
    if: always()
    needs: [router]
    runs-on: ubuntu-latest
    steps: [{run: echo ok}]
  gated:
    name: CI Gated
    if: needs.router.outputs.run == 'true'
    needs: [router]
    runs-on: ubuntu-latest
    steps: [{run: echo ok}]
""",
    "docs.yml": """
name: Docs Only
on:
  pull_request:
    paths: ['docs/**']
jobs:
  docs-build:
    runs-on: ubuntu-latest
    steps: [{run: echo ok}]
""",
    "nightly.yml": """
name: Nightly Audit
on:
  schedule:
    - cron: '0 3 * * *'
jobs:
  nightly:
    name: Nightly Job
    runs-on: ubuntu-latest
    steps: [{run: echo ok}]
""",
    "develop-only.yml": """
name: Develop Only
on:
  pull_request:
    branches: [develop]
jobs:
  develop-check:
    name: Develop Check
    runs-on: ubuntu-latest
    steps: [{run: echo ok}]
""",
    "matrix.yml": """
name: Matrix Suite
on:
  pull_request:
jobs:
  matrix-job:
    name: Matrix Job
    strategy:
      matrix:
        python: ['3.11', '3.12']
    runs-on: ubuntu-latest
    steps: [{run: echo ok}]
""",
    "broken.yml": """
name: Broken
on: [pull_request
jobs: {}
""",
}


@pytest.fixture
def inventory(tmp_path: Path) -> dict:
    workflow_dir = tmp_path / "workflows"
    workflow_dir.mkdir()
    for name, content in WORKFLOWS.items():
        (workflow_dir / name).write_text(content, encoding="utf-8")
    return build_workflow_inventory(workflow_dir, target_branch="main")


def report_for(inventory: dict, **policy) -> dict:
    return build_report(policy=policy, inventory=inventory, target_branch="main")


def status_of(report: dict, context: str) -> str:
    return next(item["status"] for item in report["classifications"] if item["context"] == context)


def classification(report: dict, context: str) -> dict:
    return next(item for item in report["classifications"] if item["context"] == context)


def test_active_contexts_include_job_name_job_id_and_always_condition(inventory):
    report = report_for(
        inventory,
        declared_required_contexts=["Required Fast Gate", "CI Result", "docs-build"],
    )
    assert status_of(report, "Required Fast Gate") == "active"
    assert status_of(report, "CI Result") == "active"
    # job sem name publica o job id, mas o workflow é filtrado por paths
    assert status_of(report, "docs-build") == "conditional_risk"


def test_workflow_name_is_not_a_check_run_name(inventory):
    report = report_for(inventory, declared_required_contexts=["ReqSys Required Fast Gate"])
    item = classification(report, "ReqSys Required Fast Gate")
    assert item["status"] == "workflow_name_mismatch"
    assert item["suggested_contexts"] == ["Required Fast Gate"]
    assert item["decision_required"] is True
    assert report["decision"] == "stale_or_misnamed_required_checks_detected"


def test_conditional_matrix_and_branch_filters_are_flagged(inventory):
    report = report_for(
        inventory,
        declared_required_contexts=["CI Gated", "Matrix Job", "Develop Check", "Nightly Job"],
    )
    assert "job_conditional_without_always" in classification(report, "CI Gated")["reasons"]
    assert "matrix_job_suffixes_context" in classification(report, "Matrix Job")["reasons"]
    assert status_of(report, "Develop Check") == "not_pr_triggered"
    assert status_of(report, "Nightly Job") == "not_pr_triggered"


def test_stale_and_renamed_candidate(inventory):
    report = report_for(inventory, declared_required_contexts=["Legacy Gate 2019", "CI Resultt"])
    assert status_of(report, "Legacy Gate 2019") == "stale"
    renamed = classification(report, "CI Resultt")
    assert renamed["status"] == "renamed_candidate"
    assert "CI Result" in renamed["suggested_contexts"]


def test_registered_decision_clears_pending_but_keeps_finding(inventory):
    policy = {
        "declared_required_contexts": ["ReqSys Required Fast Gate"],
        "recommended_required_contexts": ["Required Fast Gate"],
        "decisions": [
            {
                "context": "ReqSys Required Fast Gate",
                "decision": "rename",
                "target_contexts": ["Required Fast Gate"],
                "rationale": "check run name real",
                "owner": "CI Governance",
                "decided_at": "2026-09-21",
            }
        ],
    }
    report = build_report(policy=policy, inventory=inventory, target_branch="main")
    assert report["summary"]["pending_decisions"] == []
    assert report["summary"]["stale_contexts"] == ["ReqSys Required Fast Gate"]
    assert report["blocking"] is False

    del policy["decisions"]
    blocked = build_report(policy=policy, inventory=inventory, target_branch="main")
    assert blocked["summary"]["pending_decisions"] == ["ReqSys Required Fast Gate"]
    assert blocked["blocking"] is True


def test_recommended_contexts_must_materialize(inventory):
    report = report_for(
        inventory,
        declared_required_contexts=["Required Fast Gate"],
        recommended_required_contexts=["Required Fast Gate", "Nightly Job"],
    )
    assert report["summary"]["recommended_all_active"] is False
    assert report["decision"] == "recommended_contexts_not_materialized"
    assert report["blocking"] is True


def test_protection_payload_has_precedence_and_fallback(inventory):
    policy = {"declared_required_contexts": ["Required Fast Gate"], "recommended_required_contexts": ["Required Fast Gate"]}
    live = build_report(
        policy=policy,
        inventory=inventory,
        protection_payload={"contexts": ["Legacy Gate"], "checks": [{"context": "CI Result"}]},
        target_branch="main",
    )
    assert live["required_contexts_source"] == "branch_protection_api"
    assert [item["context"] for item in live["classifications"]] == ["CI Result", "Legacy Gate"]

    unavailable = build_report(
        policy=policy,
        inventory=inventory,
        protection_payload={"unavailable": True, "reason": "403"},
        target_branch="main",
    )
    assert unavailable["required_contexts_source"] == "versioned_baseline_protection_unavailable"
    assert unavailable["decision"] == "required_checks_aligned"


def test_no_declared_context_is_inconclusive(inventory):
    report = report_for(inventory, declared_required_contexts=[])
    assert report["inconclusive"] is True
    assert report["decision"] == "no_required_contexts_declared"
    assert report["blocking"] is True


def test_unparsed_workflow_is_reported_without_breaking(inventory):
    assert inventory["unparsed_files"] == ["broken.yml"]


def test_report_never_authorizes_automatic_protection_change(inventory):
    report = report_for(inventory, declared_required_contexts=["Required Fast Gate"])
    assert report["automatic_branch_protection_change_allowed"] is False
    assert report["automatic_context_removal_allowed"] is False
    assert report["production_touched"] is False


def test_normalize_ignores_accents_and_separators():
    assert normalize("Governança — Padrão Ouro") == normalize("governanca padrao ouro")


def test_real_repository_policy_is_consistent():
    policy = load_json(DEFAULT_POLICY)
    inventory = build_workflow_inventory(DEFAULT_WORKFLOW_DIR, target_branch=policy["target_branch"])
    report = build_report(policy=policy, inventory=inventory, target_branch=policy["target_branch"])
    assert report["summary"]["recommended_all_active"] is True, report["recommended_validation"]
    assert report["summary"]["pending_decisions"] == []
    assert report["blocking"] is False
    for decision in policy["decisions"]:
        assert decision["target_contexts"], decision["context"]
        assert decision["owner"] and decision["decided_at"] and decision["rationale"]
