from pathlib import Path


WORKFLOW = Path(".github/workflows/fly-enterprise-sync.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_requested_deploy_cannot_finish_green_when_sync_is_skipped() -> None:
    text = _workflow_text()

    assert "name: Garantir resultado coerente com a solicitação" in text
    assert 'DEPLOY_REQUESTED: ${{ github.event.inputs.deploy || \'false\' }}' in text
    assert 'if [ "$SHOULD_DEPLOY" != "true" ]; then' in text
    assert 'if [ "$SYNC_RESULT" != "success" ]; then' in text
    assert "Deploy solicitado, mas o job Sync terminou" in text


def test_sync_runs_after_non_applicable_gate_is_skipped() -> None:
    text = _workflow_text()
    block = text.split("\n  sync-environment:\n", 1)[1].split(
        "\n  runtime-smoke-readonly:\n", 1
    )[0]

    assert "needs: [validate-manifest, plan-environments]" in block
    assert "always() &&" in block
    assert "needs.validate-manifest.result == 'success'" in block
    assert "needs.plan-environments.result == 'success'" in block
    assert "needs.plan-environments.outputs.should_deploy == 'true'" in block


def test_post_deploy_publication_drift_is_a_hard_failure() -> None:
    text = _workflow_text()
    block = text.split("- name: Validar publicação sincronizada", 1)[1].split(
        "- name: Validar login do ambiente", 1
    )[0]

    assert "continue-on-error: true" not in block
    assert "validate_publication_sync.py" in block
    assert "|| true" not in block
    assert "::error::Publication sync com drift" in block
    assert "exit 1" in block
