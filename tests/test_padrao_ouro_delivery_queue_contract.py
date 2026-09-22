from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_WORKFLOW = REPO_ROOT / ".github/workflows/padrao-ouro-delivery-automation.yml"
QUEUE_GUARD_WORKFLOW = REPO_ROOT / ".github/workflows/padrao-ouro-delivery-queue-guard.yml"


def test_delivery_workflow_has_single_merge_trigger() -> None:
    workflow = DELIVERY_WORKFLOW.read_text(encoding="utf-8")

    assert "\n  pull_request:\n" not in workflow
    assert (
        "group: padrao-ouro-delivery-${{ github.event_name }}-${{ github.ref_name }}"
        in workflow
    )
    assert "cancel-in-progress: false" in workflow


def test_queue_guard_cancels_only_stale_or_superseded_runs() -> None:
    guard = QUEUE_GUARD_WORKFLOW.read_text(encoding="utf-8")

    assert "actions: write" in guard
    assert 'const staleMinutes = 10;' in guard
    assert 'run.event === "pull_request"' in guard
    assert "const superseded = newerSameStream" in guard
    assert "cancelWorkflowRun" in guard
