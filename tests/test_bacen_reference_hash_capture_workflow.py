from pathlib import Path


WORKFLOW = Path(".github/workflows/bacen-reference-hash-capture.yml")


def test_external_hash_drift_does_not_block_workflow_only_pr():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Resolve strict verification scope" in text
    assert 'reason="workflow_runtime_only"' in text
    assert "normative_input_changed" in text
    assert "steps.scope.outputs.strict" in text
    assert "args+=(--verify)" in text
    assert "External BACEN reference drift detected outside normative PR scope" in text


def test_normative_inputs_remain_fail_closed():
    text = WORKFLOW.read_text(encoding="utf-8")

    for path in (
        "governance/bacen/normative/NORMATIVE-BASELINE-V2\\.yaml",
        "scripts/capture_bacen_reference_hashes\\.py",
        "scripts/validate_bacen_normative_axis\\.py",
    ):
        assert path in text

    assert "strict=true" in text
    assert 'if [[ "${{ github.event_name }}" == "pull_request" ]]' in text
    assert 'if [[ "${{ steps.scope.outputs.strict }}" == "true" ]]' in text
