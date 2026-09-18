from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "governed-merge-queue.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_governed_merge_queue_runs_sdd_on_exact_pr_sha() -> None:
    text = workflow_text()
    assert "sdd-contract:" in text
    assert "SDD — contrato da mudança no SHA do PR" in text
    assert 'HEAD_SHA: ${{ needs.resolve-context.outputs.head_sha }}' in text
    assert 'BASE_REF: ${{ needs.resolve-context.outputs.base_ref }}' in text
    assert "python scripts/sdd_gate.py" in text
    assert '--base-ref "$BASE_REF"' in text
    assert '--head-sha "$HEAD_SHA"' in text


def test_merge_eligibility_fails_closed_on_sdd_result() -> None:
    text = workflow_text()
    assert (
        "needs: [resolve-context, sdd-contract, isolated-validation, "
        "temporary-integration, current-sha-stability]"
    ) in text
    assert 'SDD="${{ needs.sdd-contract.result }}"' in text
    assert '[ "$SDD" != "success" ]' in text
    assert "--arg sdd_contract_result" in text
    assert "sdd_contract: $sdd_contract_result" in text
