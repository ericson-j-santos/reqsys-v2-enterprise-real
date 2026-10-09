from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/codex-worker-pool-handoff.yml"


def _powershell_summary_block() -> str:
    raw = WORKFLOW.read_text(encoding="utf-8")
    return raw.split("      - name: Resumo", maxsplit=1)[1].split(
        "  portable-contract-e2e:", maxsplit=1
    )[0]


def test_summary_uses_environment_inputs_without_ambiguous_backticks() -> None:
    summary = _powershell_summary_block()

    assert "SUMMARY_ISSUE_NUMBER: ${{ inputs.issue_number }}" in summary
    assert "SUMMARY_BASE_SHA: ${{ inputs.base_sha }}" in summary
    assert "SUMMARY_REQUEST_ID: ${{ inputs.request_id }}" in summary
    assert "`${{ inputs.base_sha }}`" not in summary
    assert "`${{ inputs.request_id }}`" not in summary
    assert "('" in summary
    assert " -f $env:SUMMARY_BASE_SHA" in summary
    assert " -f $env:SUMMARY_REQUEST_ID" in summary


def test_summary_preserves_governed_handoff_metadata() -> None:
    summary = _powershell_summary_block()

    assert "- Issue: #{0}" in summary
    assert "- Base SHA: {0}" in summary
    assert "- Request ID: {0}" in summary
    assert "- Executor: codex_worker_pool" in summary
    assert "- Modo: branch-first" in summary
    assert "- PR automática: não" in summary
    assert "- Merge/deploy: não" in summary
    assert "- Token exposto: não" in summary
