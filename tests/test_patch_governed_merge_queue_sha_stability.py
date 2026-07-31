from pathlib import Path

import pytest

from scripts.patch_governed_merge_queue_sha_stability import patch_workflow


WORKFLOW = Path(".github/workflows/governed-merge-queue.yml")


def test_patches_real_workflow_once() -> None:
    patched = patch_workflow(WORKFLOW.read_text(encoding="utf-8"))
    assert patched.count("REQSYS_CURRENT_SHA_STABILITY_GATE") == 1
    assert patched.count("  current-sha-stability:\n") == 1
    assert "temporary-integration, current-sha-stability" in patched
    assert "current-sha-workflow-stability" in patched
    assert "current_sha_stability: $sha_stability[0]" in patched
    assert "Estabilidade do SHA atual" in patched


def test_rejects_already_patched_workflow() -> None:
    patched = patch_workflow(WORKFLOW.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="already present"):
        patch_workflow(patched)


def test_rejects_missing_anchor() -> None:
    with pytest.raises(ValueError):
        patch_workflow("name: incomplete\n")
