"""Caminhos críticos — external sources registry."""

from __future__ import annotations

import json

import pytest

import app.services.external_sources_registry as module
from app.core import config as config_module
from app.services.external_sources_registry import (
    carregar_registry,
    registry_default_ttl,
    resumo_fontes_externas,
    validar_registry_producao,
)


def test_carregar_registry_retorna_vazio_quando_arquivo_ausente(monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'REGISTRY_PATH', tmp_path / 'ausente.json')
    registry = carregar_registry()
    assert registry['sources'] == []
    assert registry['policy']['allow_mock_in_production'] is False


def test_registry_default_ttl_usa_policy(monkeypatch, tmp_path):
    path = tmp_path / 'registry.json'
    path.write_text(
        json.dumps({'policy': {'default_ttl_minutes': 30}, 'sources': []}),
        encoding='utf-8',
    )
    monkeypatch.setattr(module, 'REGISTRY_PATH', path)
    assert registry_default_ttl() == 30


def test_validar_registry_producao_bloqueia_mock_as_real(monkeypatch, tmp_path):
    path = tmp_path / 'registry.json'
    path.write_text(
        json.dumps(
            {
                'policy': {'allow_mock_in_production': False},
                'sources': [{'id': 'mock-fonte', 'mock_as_real': True}],
            }
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(module, 'REGISTRY_PATH', path)
    monkeypatch.setattr(config_module.settings, 'app_environment', 'production')
    with pytest.raises(RuntimeError, match='mock_as_real'):
        validar_registry_producao()


def test_validar_registry_producao_bloqueia_allow_mock_policy(monkeypatch, tmp_path):
    path = tmp_path / 'registry.json'
    path.write_text(
        json.dumps({'policy': {'allow_mock_in_production': True}, 'sources': []}),
        encoding='utf-8',
    )
    monkeypatch.setattr(module, 'REGISTRY_PATH', path)
    monkeypatch.setattr(config_module.settings, 'app_environment', 'production')
    with pytest.raises(RuntimeError, match='allow_mock_in_production'):
        validar_registry_producao()


def test_listar_fontes_externas_conta_nao_autorizadas(monkeypatch, tmp_path):
    path = tmp_path / 'registry.json'
    path.write_text(
        json.dumps(
            {
                'policy': {'default_ttl_minutes': 1440},
                'sources': [
                    {
                        'id': 'pendente',
                        'nome': 'Fonte pendente',
                        'origem': 'test',
                        'ttlMinutos': 60,
                        'autorizado': False,
                        'mock_as_real': False,
                    }
                ],
            }
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(module, 'REGISTRY_PATH', path)
    resumo = resumo_fontes_externas()
    assert resumo['pendentes_auditoria'] == 1
    assert resumo['autorizadas_validas'] == 0
