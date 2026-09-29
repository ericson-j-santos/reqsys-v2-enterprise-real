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


def test_main_post_merge_validation_is_report_only_except_explicit_dispatch() -> None:
    workflow = _workflow_text()

    assert "context.eventName === 'workflow_dispatch'" in workflow
    assert "'blocking_dispatch'" in workflow
    assert "'report_only'" in workflow
    assert "Enforce dispatched post-merge gate" in workflow
    assert "MAIN_POST_MERGE_GATE_NOT_PASSED" in workflow
    assert "if: always() && github.event_name == 'workflow_dispatch'" in workflow
    assert "core.warning" in workflow
    assert "core.setOutput('status', gate.status)" in workflow


def test_main_post_merge_validation_enforces_security_delta_on_exact_sha() -> None:
    workflow = _workflow_text()

    assert "Checkout validated main SHA" in workflow
    assert "ref: ${{ steps.evidence.outputs.validated_sha }}" in workflow
    assert 'actual_sha="$(git rev-parse HEAD)"' in workflow
    assert 'parent_sha="$(git rev-parse "${VALIDATED_SHA}^1")"' in workflow
    assert 'diff_range="${parent_sha}...${VALIDATED_SHA}"' in workflow
    assert "audit/security-post-merge/changed-files.txt" in workflow
    assert "audit/security-post-merge/changed-lines.json" in workflow
    assert "Enforce security delta on exact main SHA" in workflow
    assert "scripts/validate_security_baseline.py" in workflow
    assert "scripts/vibe_security_gate.py" in workflow
    assert "--strict" in workflow
    assert "--scope changed" in workflow


def test_main_post_merge_validation_keeps_full_security_posture_report_only() -> None:
    workflow = _workflow_text()

    section = workflow.split(
        "- name: Snapshot full security posture on exact main SHA", maxsplit=1
    )[1].split("- name: Upload main validation evidence", maxsplit=1)[0]

    assert "--scope all" in section
    assert "--strict" not in section
    assert "audit/security-post-merge/posture/baseline" in section
    assert "audit/security-post-merge/posture/vibe-security" in section
