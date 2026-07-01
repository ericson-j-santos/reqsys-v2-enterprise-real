from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/main-post-merge-validation.yml")


def _workflow_text() -> str:
    assert WORKFLOW.exists(), "Main post-merge validation workflow must exist."
    return WORKFLOW.read_text(encoding="utf-8")


def test_main_post_merge_validation_discovers_runs_by_head_sha() -> None:
    workflow = _workflow_text()

    assert "github.rest.actions.listWorkflowRunsForRepo" in workflow
    assert "head_sha: headSha" in workflow
    assert "per_page: 100" in workflow
    assert "workflow_runs: runs" in workflow


def test_main_post_merge_validation_collects_artifacts_for_discovered_runs() -> None:
    workflow = _workflow_text()

    assert "github.rest.actions.listWorkflowRunArtifacts" in workflow
    assert "run_id: run.id" in workflow
    assert "artifacts: artifacts.map" in workflow
    assert "digest: artifact.digest || null" in workflow


def test_main_post_merge_validation_publishes_navigable_evidence_artifact() -> None:
    workflow = _workflow_text()

    assert "audit/main-post-merge-validation.json" in workflow
    assert "audit/main-post-merge-validation.md" in workflow
    assert "name: main-post-merge-validation-${{ steps.evidence.outputs.validated_sha || github.sha }}" in workflow
    assert "retention-days: 30" in workflow


def test_main_post_merge_validation_keeps_report_only_contract() -> None:
    workflow = _workflow_text()

    assert "mode: 'report_only'" in workflow
    assert "core.warning" in workflow
    assert "if (gate.status !== 'passed')" in workflow
    assert "core.setOutput('status', gate.status)" in workflow
