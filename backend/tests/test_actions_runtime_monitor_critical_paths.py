"""Caminhos críticos — monitor de GitHub Actions runtime."""

from unittest.mock import patch

import pytest

from app.services.actions_runtime_monitor import (
    WorkflowRunSnapshot,
    classificar_runs,
    decidir_estado,
    normalizar_run,
)


def _run(**kwargs) -> WorkflowRunSnapshot:
    base = {
        'run_id': 1,
        'workflow': 'CI',
        'status': 'completed',
        'conclusion': 'success',
        'branch': 'main',
        'event': 'push',
        'commit_sha': 'abc',
        'html_url': 'https://example.com',
        'created_at': '2026-01-01T00:00:00Z',
        'updated_at': '2026-01-01T00:05:00Z',
    }
    base.update(kwargs)
    return WorkflowRunSnapshot(**base)


def test_normalizar_run_usa_defaults():
    snapshot = normalizar_run({'id': 9})
    assert snapshot.workflow == 'workflow-desconhecido'
    assert snapshot.status == 'unknown'


def test_workflow_run_health_running_e_unhealthy():
    running = _run(status='in_progress', conclusion=None)
    failed = _run(conclusion='failure')
    assert running.health == 'running'
    assert failed.health == 'unhealthy'


def test_decidir_estado_prioriza_falhas():
    assert decidir_estado(100, [_run(conclusion='failure')], []) == 'corrigir_falhas_de_actions_antes_de_novo_merge'


def test_decidir_estado_aguarda_execucao():
    assert decidir_estado(100, [], [_run(status='queued', conclusion=None)]) == 'aguardar_finalizacao_dos_workflows'


def test_classificar_runs_calcula_score_e_decisao():
    resultado = classificar_runs([_run(), _run(conclusion='failure')])
    assert resultado['total_runs'] == 2
    assert resultado['score_saude'] == 50.0
    assert resultado['decisao'] == 'corrigir_falhas_de_actions_antes_de_novo_merge'


def test_decidir_estado_operacao_estavel():
    assert decidir_estado(96, [], []) == 'operacao_estavel'


def test_decidir_estado_investigar_instabilidade():
    assert decidir_estado(80, [], []) == 'investigar_instabilidade_operacional'


@patch('app.services.actions_runtime_monitor.requests.get')
def test_github_actions_client_listar_runs(mock_get, monkeypatch):
    from app.services.actions_runtime_monitor import GitHubActionsClient

    monkeypatch.setenv('GITHUB_TOKEN', 'ghp_test_token')
    mock_get.return_value.json.return_value = {
        'workflow_runs': [{'id': 1, 'name': 'CI', 'status': 'completed', 'conclusion': 'success'}],
    }
    mock_get.return_value.raise_for_status = lambda: None

    client = GitHubActionsClient()
    runs = client.listar_runs('owner/repo', branch='main', per_page=5)

    assert len(runs) == 1
    assert runs[0].workflow == 'CI'


def test_github_actions_client_exige_token(monkeypatch):
    from app.services.actions_runtime_monitor import GitHubActionsClient

    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    monkeypatch.delenv('REQSYS_GITHUB_TOKEN', raising=False)

    client = GitHubActionsClient(token=None)

    with pytest.raises(RuntimeError, match='GITHUB_TOKEN'):
        client.listar_runs('owner/repo')
