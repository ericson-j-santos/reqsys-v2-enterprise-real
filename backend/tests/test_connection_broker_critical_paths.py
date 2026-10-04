"""Testes de caminhos críticos — connection broker (registry local e resumo operacional)."""

import json
from pathlib import Path
from unittest.mock import patch

from app.services import connection_broker as broker


def test_listar_conectores_ignora_capabilities_invalidas(tmp_path, monkeypatch):
    registry = {
        'version': '9.9.9',
        'capabilities': [
            {'ambiente': 'dev', 'conector': 'sql', 'capability': 'read', 'status': 'ready', 'criticidade': 'high'},
            'invalido',
        ],
    }
    registry_path = tmp_path / 'connection-broker-registry.json'
    registry_path.write_text(json.dumps(registry), encoding='utf-8')
    monkeypatch.setattr(broker, 'REGISTRY_PATH', registry_path)

    conectores = broker.listar_conectores()

    assert len(conectores) == 1
    assert conectores[0]['status'] == 'ready'
    assert conectores[0]['requires_human_confirmation'] is False


def test_resumo_conectores_classifica_estados():
    conectores = [
        {'status': 'ready'},
        {'status': 'missing_permission'},
        {'status': 'blocked'},
    ]

    resumo = broker.resumo_conectores(conectores)

    assert resumo['total'] == 3
    assert resumo['prontos'] == 1
    assert resumo['pendentes'] == 1
    assert resumo['bloqueados'] == 1
    assert resumo['estado_geral'] == 'bloqueado'


def test_resumo_conectores_estado_desconhecido_quando_vazio():
    resumo = broker.resumo_conectores([])

    assert resumo['estado_geral'] == 'desconhecido'
    assert resumo['total'] == 0


def test_listar_conectores_sem_registry_retorna_lista_vazia(tmp_path, monkeypatch):
    monkeypatch.setattr(broker, 'REGISTRY_PATH', tmp_path / 'ausente.json')

    assert broker.listar_conectores() == []


def test_resumo_conectores_estado_amarelo_quando_apenas_pendentes():
    resumo = broker.resumo_conectores([{'status': 'missing_permission'}, {'status': 'expired'}])

    assert resumo['pendentes'] == 2
    assert resumo['estado_geral'] == 'amarelo'


def test_resumo_conectores_estado_verde_quando_apenas_prontos():
    resumo = broker.resumo_conectores([{'status': 'ready'}, {'status': 'ready'}])

    assert resumo['prontos'] == 2
    assert resumo['estado_geral'] == 'verde'


def test_montar_health_payload_expoe_registry_version(monkeypatch):
    registry_path = Path(broker.REGISTRY_PATH)
    if not registry_path.is_file():
        monkeypatch.setattr(
            broker,
            '_carregar_registry',
            lambda: {'version': '1.0.0', 'capabilities': []},
        )

    payload = broker.montar_health_payload('corr-broker-001')

    assert payload['correlation_id'] == 'corr-broker-001'
    assert 'resumo' in payload
    assert payload['registry_version']
