from pathlib import Path


WORKFLOW = Path(".github/workflows/actions-dispatcher.yml")


def _text() -> str:
    assert WORKFLOW.exists()
    return WORKFLOW.read_text(encoding="utf-8")


def test_materializer_is_event_driven_and_exact_sha_scoped() -> None:
    text = _text()

    assert "repository_dispatch:" in text
    assert "governed_post_merge_validation" in text
    assert "github.event.inputs.mode == 'post-merge'" in text
    assert "schedule:" not in text
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


def test_materializer_dispatches_required_exact_sha_workflows() -> None:
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


def test_touched_dispatcher_actions_are_immutable() -> None:
    text = _text()

    assert "actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3" in text
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in text
    assert "actions/github-script@v7" not in text
    assert "actions/upload-artifact@v4" not in text


def test_materializer_exposes_runtime_replay_and_negative_controls() -> None:
    text = _text()

    assert "test_case:" in text
    assert "['normal', 'replay', 'missing-required-workflow']" in text
    assert "__missing-required-workflow-control__.yml" in text
    assert "Missing Required Workflow — negative control" in text
    assert "NEGATIVE_CONTROL_REQUIRED_WORKFLOW_MISSING" in text
    assert "dispatches_created" in text
    assert "reused_run_ids" in text
    assert "negative_control_detected" in text


def test_materializer_replay_reuses_success_and_negative_control_fails_closed() -> None:
    text = _text()

    assert "evidence.reused_run_ids.push(state.run.id)" in text
    assert "evidence.reused_run_ids.push(existingMain.run.id)" in text
    assert "evidence.dispatches_created.push(workflow.name)" in text
    assert "evidence.dispatches_created.push(mainValidation.name)" in text
    assert "workflow.negative_control === true" in text
    assert "core.setFailed(evidence.error_code)" in text
