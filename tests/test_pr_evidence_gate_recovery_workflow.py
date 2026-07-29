from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/pr-evidence-gate-recovery.yml")


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_recovery_runs_only_after_successful_pull_request_ci() -> None:
    workflow = _workflow_text()

    assert "workflow_run:" in workflow
    assert "CI — ReqSys v2 Enterprise" in workflow
    assert "github.event.workflow_run.event == 'pull_request'" in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow


def test_recovery_has_minimum_required_permissions() -> None:
    workflow = _workflow_text()

    assert "actions: write" in workflow
    assert "contents: read" in workflow
    assert "pull-requests: write" not in workflow


def test_recovery_is_idempotent_and_targets_only_failed_evidence_gate() -> None:
    workflow = _workflow_text()

    assert "run.name === 'PR Evidence Gate'" in workflow
    assert "run.conclusion === 'success'" in workflow
    assert "run.status !== 'completed'" in workflow
    assert "run.conclusion === 'failure'" in workflow
    assert "reRunWorkflowFailedJobs" in workflow
