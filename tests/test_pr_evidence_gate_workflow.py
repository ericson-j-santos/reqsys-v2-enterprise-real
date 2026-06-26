from pathlib import Path

WORKFLOW = Path('.github/workflows/pr-evidence-gate.yml')


def read_workflow() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_pr_evidence_gate_keeps_full_wait_window_after_fast_poll_change():
    text = read_workflow()

    assert "MAX_WAIT_SECONDS: '180'" in text
    assert "POLL_SECONDS: '15'" in text
    assert "MAX_WAIT_SECONDS: '45'" not in text
    assert "POLL_SECONDS: '5'" not in text


def test_pr_evidence_gate_lists_artifacts_only_after_gate_passes():
    text = read_workflow()

    assert 'async function listRuns(headSha, includeArtifacts = false)' in text
    assert "if (includeArtifacts && run.status === 'completed')" in text
    assert 'runSummaries = await listRuns(headSha, false);' in text
    assert "if (gate.status === 'passed')" in text
    assert 'runSummaries = await listRuns(headSha, true);' in text

    polling_index = text.index('runSummaries = await listRuns(headSha, false);')
    artifact_index = text.index('runSummaries = await listRuns(headSha, true);')
    assert polling_index < artifact_index
