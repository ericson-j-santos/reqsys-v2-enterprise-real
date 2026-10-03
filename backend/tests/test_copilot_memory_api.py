"""Testes de API da memória persistente Copilot/Planner/Excel (#1359)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.copilot_memory import require_copilot_memory_auth
from app.core.service_tokens import ServiceAuthContext
from app.main import app

client = TestClient(app)


def _fake_ctx():
    return ServiceAuthContext(ator='admin@teste', via_token=False)


@pytest.fixture
def auth_override():
    app.dependency_overrides[require_copilot_memory_auth] = _fake_ctx
    yield
    app.dependency_overrides.pop(require_copilot_memory_auth, None)


def _payload():
    return {
        'items': [
            {
                'plannerTaskId': 'task-api-1',
                'origem': 'planner',
                'plannerTitulo': 'Tarefa de teste',
                'plannerStatus': 'em_andamento',
                'plannerPercentual': 20,
                'plannerPrazo': '2026-09-10',
            }
        ]
    }


def test_sync_sem_auth_retorna_401_ou_403():
    response = client.post('/v1/hub-lowcode/copilot-memory/sync', json=_payload())
    assert response.status_code in (401, 403)


@patch('app.api.copilot_memory.sincronizar_lote')
def test_sync_happy_path(mock_sync, auth_override):
    mock_sync.return_value = {
        'items': [{'memoryId': 'mem-1', 'changed': True}],
        'total': 1,
        'alterados': 1,
        'inalterados': 0,
        'correlationId': 'corr-api',
    }
    response = client.post(
        '/v1/hub-lowcode/copilot-memory/sync',
        json=_payload(),
        headers={'X-Correlation-ID': 'corr-api'},
    )
    assert response.status_code == 200
    assert response.json()['data']['total'] == 1
    assert response.json()['data']['alterados'] == 1


def test_sync_sem_identificador_retorna_422(auth_override):
    payload = _payload()
    payload['items'][0].pop('plannerTaskId')
    response = client.post('/v1/hub-lowcode/copilot-memory/sync', json=payload)
    assert response.status_code == 422


@patch('app.api.copilot_memory.listar_memorias')
def test_export_retorna_formato_tabular(mock_listar, auth_override):
    mock_listar.return_value = [
        {'memoryId': 'mem-1', 'plannerTaskId': 'task-1', 'assunto': 'Teste'},
        {'memoryId': 'mem-2', 'plannerTaskId': 'task-2', 'assunto': 'Teste 2'},
    ]
    response = client.get('/v1/hub-lowcode/copilot-memory/export')
    assert response.status_code == 200
    assert response.json()['data']['total'] == 2


@patch('app.api.copilot_memory.listar_comandos_planner')
def test_planner_commands_lista_somente_pendentes_do_servico(mock_listar, auth_override):
    mock_listar.return_value = [
        {
            'memoryId': 'mem-1',
            'plannerTaskId': 'task-1',
            'plannerTitulo': 'Atualizar título',
            'plannerStatus': 'em_andamento',
            'plannerPercentual': 50,
            'plannerPrazo': '2026-09-10',
            'desiredHash': 'hash-1',
            'correlationId': 'corr-1',
        }
    ]
    response = client.get('/v1/hub-lowcode/copilot-memory/planner-commands')
    assert response.status_code == 200
    assert response.json()['data']['total'] == 1


@patch('app.api.copilot_memory.confirmar_comando_planner')
def test_planner_ack_sucesso(mock_ack, auth_override):
    mock_ack.return_value = {
        'memoryId': 'mem-1',
        'plannerTaskId': 'task-1',
        'plannerSyncStatus': 'sincronizado',
        'atualizarPlanner': False,
    }
    response = client.post(
        '/v1/hub-lowcode/copilot-memory/mem-1/planner-ack',
        json={'sucesso': True, 'plannerTaskId': 'task-1'},
    )
    assert response.status_code == 200
    assert response.json()['data']['plannerSyncStatus'] == 'sincronizado'


@patch('app.api.copilot_memory.confirmar_comando_planner')
def test_planner_ack_inexistente_retorna_404(mock_ack, auth_override):
    mock_ack.side_effect = ValueError('Memória mem-x não encontrada')
    response = client.post(
        '/v1/hub-lowcode/copilot-memory/mem-x/planner-ack',
        json={'sucesso': True},
    )
    assert response.status_code == 404
