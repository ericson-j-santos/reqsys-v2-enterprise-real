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
    if "absence_is_success" in workflow:
        assert '"absence_is_success": False' in workflow


def test_stability_evidence_is_persisted() -> None:
    workflow = workflow_path().read_text(encoding="utf-8")
    assert "current-sha-stability.json" in workflow
    assert "current-sha-workflow-stability" in workflow
    assert "current_sha_stability: $sha_stability[0]" in workflow


def test_current_sha_run_discovery_paginates_all_workflows() -> None:
    workflow = workflow_path().read_text(encoding="utf-8")
    assert "gh api --method GET --paginate --slurp" in workflow
    assert "workflow_runs: [.[].workflow_runs[]]" in workflow


def test_final_gate_tolerates_missing_stability_artifact() -> None:
    workflow = workflow_path().read_text(encoding="utf-8")
    assert "Baixar evidência de estabilidade do SHA atual" in workflow
    assert "continue-on-error: true" in workflow
    assert "Garantir fallback de estabilidade do SHA" in workflow
    assert "stability_artifact_missing" in workflow


def test_base_head_stability_is_fail_closed() -> None:
    workflow = workflow_path().read_text(encoding="utf-8")
    assert "base-head-stability:" in workflow
    assert "current_base_sha" in workflow
    assert "branch_sha" in workflow
    assert "compare_status" in workflow
    assert "PR atrasada ou divergente" in workflow



def test_missing_context_never_calls_issue_zero() -> None:
    """An absent or cancelled context must not drive issue/0 labels API."""
    workflow = workflow_path().read_text(encoding="utf-8")
    sync = workflow.partition("      - name: Sincronizar label de elegibilidade")[2].partition(
        "      - name: Publicar evidência de política"
    )[0]
    assert "needs.resolve-context.result == 'success'" in sync
    assert "needs.resolve-context.outputs.pr_number != ''" in sync
    assert "needs.resolve-context.outputs.pr_number != '0'" in sync
    assert "Number.isSafeInteger(prNumber)" in sync
    assert "prNumber < 1" in sync
    assert "return;" in sync
    assert "issue_number: prNumber" in sync


def test_missing_pr_number_does_not_create_false_eligibility() -> None:
    """Absent PR number becomes null in the failure receipt; gate remains red."""
    workflow = workflow_path().read_text(encoding="utf-8")
    policy = workflow.partition("      - name: Consolidar política e elegibilidade")[2].partition(
        "      - name: Sincronizar label de elegibilidade"
    )[0]
    assert "pr_number: (try ($pr_number | tonumber) catch null)" in policy
    assert 'if [ "$SDD" != "success" ]' in policy
    assert 'CI_STATUS="red"' in policy
    assert 'if [ "$ELIGIBLE" != "true" ]; then' in policy
    assert "exit 1" in policy
