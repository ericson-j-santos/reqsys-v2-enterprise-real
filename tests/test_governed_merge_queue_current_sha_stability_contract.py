import os
from pathlib import Path


def workflow_path() -> Path:
    return Path(
        os.environ.get(
            "GOVERNED_MERGE_QUEUE_WORKFLOW_PATH",
            ".github/workflows/governed-merge-queue.yml",
        )
    )


def test_current_sha_stability_is_required_before_final_gate() -> None:
    workflow = workflow_path().read_text(encoding="utf-8")
    stability = workflow.index("\n  current-sha-stability:\n")
    final_gate = workflow.index("\n  merge-queue-gate:\n")
    assert stability < final_gate
    assert "temporary-integration, current-sha-stability" in workflow
    assert "needs.current-sha-stability.result" in workflow


def test_absence_or_pending_workflows_cannot_be_eligible() -> None:
    workflow = workflow_path().read_text(encoding="utf-8")
    assert "evaluate_current_sha_workflow_stability.py" in workflow
    assert "head_sha_changed" in workflow
    assert "Os workflows críticos não estabilizaram" in workflow
    assert "absence_is_success" not in workflow


def test_stability_evidence_is_persisted() -> None:
    workflow = workflow_path().read_text(encoding="utf-8")
    assert "current-sha-stability.json" in workflow
    assert "current-sha-workflow-stability" in workflow
    assert "current_sha_stability: $sha_stability[0]" in workflow
