from pathlib import Path


WORKFLOW = Path(".github/workflows/governed-post-merge-materializer.yml")


def _text() -> str:
    assert WORKFLOW.exists()
    return WORKFLOW.read_text(encoding="utf-8")


def test_materializer_is_event_driven_and_exact_sha_scoped() -> None:
    text = _text()

    assert "repository_dispatch:" in text
    assert "governed_post_merge_validation" in text
    assert "schedule:" not in text
    assert "merge_sha" in text
    assert "head_sha: mergeSha" in text
    assert "MERGE_SHA_DOES_NOT_MATCH_PR" in text
    assert "HEAD_SHA_DOES_NOT_MATCH_PR" in text


def test_materializer_uses_temporary_ref_and_cleans_it() -> None:
    text = _text()

    assert "github.rest.git.createRef" in text
    assert "post-merge-validation/" in text
    assert "github.rest.git.deleteRef" in text
    assert "TEMP_REF_SHA_MISMATCH" in text
    assert "TEMP_REF_CLEANUP_FAILED" in text


def test_materializer_dispatches_only_required_exact_sha_workflows() -> None:
    text = _text()

    for workflow in (
        "ci.yml",
        "governance-quality-gates.yml",
        "governanca-padrao-ouro.yml",
        "main-post-merge-validation.yml",
    ):
        assert workflow in text

    assert "github.rest.actions.createWorkflowDispatch" in text
    assert "inputs: { commit_sha: mergeSha }" in text
    assert "workflow_dispatch" in text


def test_materializer_is_replay_safe_and_fail_closed() -> None:
    text = _text()

    assert "classify(matchingRuns" in text
    assert "EXISTING_POST_MERGE_FAILURE" in text
    assert "EXISTING_MAIN_VALIDATION_FAILURE" in text
    assert "POST_MERGE_WORKFLOW_TIMEOUT" in text
    assert "cancel-in-progress: false" in text
    assert "replay_safe: true" in text
