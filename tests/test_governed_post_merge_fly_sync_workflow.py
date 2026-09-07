from pathlib import Path


WORKFLOW = Path(".github/workflows/governed-post-merge-fly-sync.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_observa_fly_enterprise_sync_concluido_na_main() -> None:
    text = _workflow_text()

    assert 'workflows: ["Fly Enterprise Sync"]' in text
    assert 'workflows: ["Governed PR Automation"]' not in text
    assert "types: [completed]" in text
    assert "branches: [main]" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event == 'push'" in text


def test_readiness_eh_somente_leitura_e_nao_concede_permissao_de_deploy() -> None:
    text = _workflow_text()

    assert "permissions:\n  contents: read" in text
    assert "actions: write" not in text
    assert "contents: write" not in text
    assert "flyctl deploy" not in text
    assert "gh workflow run" not in text
    assert "createDispatchEvent" not in text
    assert '"deploy_executed": False' in text


def test_drift_gera_evidencia_sem_falhar_ou_promover_ambiente() -> None:
    text = _workflow_text()

    assert "validate_fly_enterprise_sync.py" in text
    assert "validate_publication_sync.py --timeout 8" in text
    assert "drift_detected_manual_dispatch_required" in text
    assert "Nenhum deploy foi executado" in text
    assert "deploy=true após validação humana" in text
    assert "export decision synced" in text


def test_evidencia_identifica_fly_enterprise_sync_como_fonte() -> None:
    text = _workflow_text()

    assert '"source_workflow": "Fly Enterprise Sync"' in text
    assert '"source_workflow": "Governed PR Automation"' not in text
    assert "SOURCE_RUN_ID: ${{ github.event.workflow_run.id || '' }}" in text
    assert "SOURCE_HEAD_SHA: ${{ github.event.workflow_run.head_sha || '' }}" in text


def test_checkout_pos_merge_observa_main_atual_e_publica_evidencia() -> None:
    text = _workflow_text()

    assert "ref: main" in text
    assert "main_sha=$(git rev-parse HEAD)" in text
    assert "source_run_id" in text
    assert "observed_main_sha" in text
    assert "governed-post-merge-fly-sync-readiness" in text
