"""Gaps de cobertura — services figma, github_branch, ai_quality, hub_lowcode, merge_readiness (fase 9)."""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.merge_readiness_history_index as merge_module
from app.core import secrets as secrets_module
from app.db import SessionLocal
from app.models.agile_runtime import AgileWorkItem
from app.services import figma_client as fc
from app.services import hub_lowcode as hub_svc
from app.services.ai_quality import calcular_resumo_qualidade_ia, listar_tendencia
from app.services.github_branch_service import GithubBranchError, criar_branch_work_item
from app.services.merge_readiness_history_index import (
    carregar_merge_readiness_history_index,
    state_para_severidade,
)


def _db_ai_quality(cobertura_count: int, incidentes_count: int):
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value = query
    query.count.side_effect = [cobertura_count, incidentes_count]
    db.query.return_value = query
    return db


@patch('app.services.ai_quality.calcular_metricas_requisitos')
def test_ai_quality_status_estavel(mock_metricas):
    mock_metricas.return_value = {
        'total': 10,
        'aprovados': 8,
        'em_analise': 1,
        'pendentes': 1,
    }
    resumo = calcular_resumo_qualidade_ia(_db_ai_quality(cobertura_count=9, incidentes_count=0))
    assert resumo['status'] in {'excelente', 'estavel'}


@patch('app.services.ai_quality.calcular_metricas_requisitos')
def test_ai_quality_recomendacao_cobertura(mock_metricas):
    mock_metricas.return_value = {
        'total': 10,
        'aprovados': 5,
        'em_analise': 2,
        'pendentes': 3,
    }
    resumo = calcular_resumo_qualidade_ia(_db_ai_quality(cobertura_count=1, incidentes_count=0))
    assert any('detalhamento' in r.lower() or 'cobertura' in r.lower() for r in resumo['recomendacoes'])


@patch('app.services.ai_quality.calcular_metricas_requisitos')
def test_ai_quality_recomendacao_seguranca(mock_metricas):
    mock_metricas.return_value = {
        'total': 5,
        'aprovados': 5,
        'em_analise': 0,
        'pendentes': 0,
    }
    resumo = calcular_resumo_qualidade_ia(_db_ai_quality(cobertura_count=5, incidentes_count=3))
    assert any('incidentes' in r.lower() or 'seguranca' in r.lower() for r in resumo['recomendacoes'])


@patch('app.services.ai_quality.calcular_metricas_requisitos')
def test_ai_quality_recomendacao_consistencia(mock_metricas):
    mock_metricas.return_value = {
        'total': 20,
        'aprovados': 2,
        'em_analise': 0,
        'pendentes': 18,
    }
    resumo = calcular_resumo_qualidade_ia(_db_ai_quality(cobertura_count=10, incidentes_count=0))
    assert any('pendencias' in r.lower() or 'consistencia' in r.lower() for r in resumo['recomendacoes'])


@patch('app.services.figma_client.request.urlopen')
def test_figma_request_json_corpo_vazio_retorna_dict(mock_urlopen, monkeypatch):
    monkeypatch.setattr(fc.settings, 'figma_access_token', 'token-test')
    mock_resp = MagicMock()
    mock_resp.read.return_value = b''
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    assert fc._request_json('GET', '/v1/files/demo') == {}


@patch('app.services.figma_client._request_json')
def test_figma_create_comment_sem_node_id(mock_request, monkeypatch):
    monkeypatch.setattr(fc.settings, 'figma_access_token', 'token-test')
    mock_request.return_value = {'id': 'c1'}

    fc.create_comment('file-key', 'mensagem')

    payload = mock_request.call_args.kwargs['payload']
    assert 'client_meta' not in payload


def _work_item() -> AgileWorkItem:
    return AgileWorkItem(
        id=1,
        codigo='AGI-900002',
        tipo='story',
        titulo='Branch gaps',
        descricao='Teste',
        prioridade='P2',
        pontos=3,
        valor_negocio=10,
        score_risco=5,
        owner_ai='backend-ia',
        status='novo',
    )


@patch('app.services.github_branch_service.montar_github_launchpad')
@patch('app.services.github_branch_service.github_client')
@patch('app.services.github_branch_service.verificar_increment_gate', return_value={'permitido': True, 'detalhe': 'ok'})
@patch('app.services.github_branch_service.github_client.github_token_configurado', return_value=True)
def test_github_branch_existente_sem_criar_levanta_erro(_token, _gate, mock_github, mock_launchpad):
    mock_launchpad.return_value = {
        'repositorio': 'org/repo',
        'branch_trabalho': 'feature/agi-900002',
        'branch_base': 'main',
        'links': {},
    }
    mock_github.get_branch_sha.return_value = 'sha-existente'

    with pytest.raises(GithubBranchError, match='ja existe'):
        criar_branch_work_item(
            MagicMock(), _work_item(), 'dev', correlation_id='corr', criar_se_ausente=False,
        )


@patch('app.services.github_branch_service.montar_github_launchpad')
@patch('app.services.github_branch_service.github_client')
@patch('app.services.github_branch_service.verificar_increment_gate', return_value={'permitido': True, 'detalhe': 'ok'})
@patch('app.services.github_branch_service.github_client.github_token_configurado', return_value=True)
def test_github_branch_existente_aplica_no_item(_token, _gate, mock_github, mock_launchpad):
    db = MagicMock()
    item = _work_item()
    mock_launchpad.return_value = {
        'repositorio': 'org/repo',
        'branch_trabalho': 'feature/agi-900002',
        'branch_base': 'main',
        'links': {},
    }
    mock_github.get_branch_sha.return_value = 'sha-existente'

    resultado = criar_branch_work_item(db, item, 'dev', correlation_id='corr', criar_se_ausente=True)

    assert resultado['motivo'] == 'branch_ja_existe'
    db.commit.assert_called_once()


@patch('app.services.github_branch_service.montar_github_launchpad')
@patch('app.services.github_branch_service.github_client')
@patch('app.services.github_branch_service.verificar_increment_gate', return_value={'permitido': True, 'detalhe': 'ok'})
@patch('app.services.github_branch_service.github_client.github_token_configurado', return_value=True)
def test_github_branch_base_ausente_levanta_erro(_token, _gate, mock_github, mock_launchpad):
    mock_launchpad.return_value = {
        'repositorio': 'org/repo',
        'branch_trabalho': 'feature/agi-900002',
        'branch_base': 'main',
        'links': {},
    }
    mock_github.get_branch_sha.return_value = None

    with pytest.raises(GithubBranchError, match='Branch base'):
        criar_branch_work_item(MagicMock(), _work_item(), 'dev', correlation_id='corr')


def test_hub_lowcode_obter_config_usa_settings_quando_db_vazio(monkeypatch):
    monkeypatch.setattr(hub_svc.settings, 'powerautomate_planner_webhook_url', 'https://example.com/hook')
    monkeypatch.setattr(hub_svc.settings, 'teams_notifications_webhook_url', 'https://example.com/teams')
    monkeypatch.setattr(hub_svc.settings, 'powerautomate_planner_webhook_key', 'key-123')

    mock_result = MagicMock()
    mock_result.scalars.return_value = []
    db = MagicMock()
    db.execute.return_value = mock_result

    cfg = hub_svc.obter_planner_webhook_config(db)

    assert cfg['webhook_url'] == 'https://example.com/hook'
    assert cfg['teams_webhook_url'] == 'https://example.com/teams'
    assert cfg['webhook_key'] == 'key-123'


def test_hub_lowcode_salvar_config_atualiza_registro_existente():
    db = SessionLocal()
    try:
        hub_svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/v1')
        hub_svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/v2')
        cfg = hub_svc.obter_planner_webhook_config(db)
        assert cfg['webhook_url'] == 'https://example.com/v2'
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_hub_lowcode_publicar_sem_correlation_id_gera_uuid(mock_client_cls):
    db = SessionLocal()
    try:
        hub_svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/planner-hook')
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {'criadas': 1, 'teams_notificado': False}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resultado = asyncio.run(
            hub_svc.publicar_tarefas_planner(db, tarefas_texto='T|D|2026-06-30|B|A|X', autor='t')
        )

        assert resultado['ok'] is True
        assert len(resultado['correlation_id']) >= 8
    finally:
        db.close()


def test_merge_readiness_json_invalido_retorna_fallback(monkeypatch, tmp_path):
    path = tmp_path / 'merge-readiness-history.json'
    path.write_text('nao-e-json', encoding='utf-8')
    monkeypatch.setattr(merge_module, 'INDEX_PATH', path)

    index = carregar_merge_readiness_history_index()

    assert index['summary']['merge_readiness_history_enabled'] is False


def test_merge_readiness_json_nao_dict_retorna_fallback(monkeypatch, tmp_path):
    path = tmp_path / 'merge-readiness-history.json'
    path.write_text(json.dumps([1, 2, 3]), encoding='utf-8')
    monkeypatch.setattr(merge_module, 'INDEX_PATH', path)

    index = carregar_merge_readiness_history_index()

    assert index['summary']['merge_readiness_history_enabled'] is False


@pytest.mark.parametrize(
    ('state', 'expected'),
    [
        ('green', 'healthy'),
        ('yellow', 'attention'),
        ('unknown', 'attention'),
        ('foo', 'attention'),
    ],
)
def test_merge_readiness_state_para_severidade(state, expected):
    assert state_para_severidade(state) == expected


class _FakeKeyringExc:
    def get_password(self, service: str, username: str) -> str | None:
        if username == '__master_key__':
            raise RuntimeError('keyring indisponivel')
        return None

    def delete_password(self, service: str, username: str) -> None:
        raise RuntimeError('delete falhou')


def test_secrets_vault_initialized_false_em_excecao(monkeypatch):
    monkeypatch.setattr(secrets_module, 'keyring', _FakeKeyringExc())
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    assert secrets_module.vault_initialized(service_name='svc-test') is False


def test_secrets_delete_false_em_excecao(monkeypatch):
    fk = _FakeKeyringExc()
    monkeypatch.setattr(secrets_module, 'keyring', fk)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    assert secrets_module.delete_secret_from_vault('KEY', service_name='svc-test') is False


def test_secrets_prefer_vault_retorna_default(monkeypatch):
    fk = _FakeKeyringExc()
    monkeypatch.setattr(secrets_module, 'keyring', fk)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    monkeypatch.setattr(secrets_module, '_CRYPTO_OK', True)
    monkeypatch.delenv('GAP_SECRET_KEY', raising=False)

    assert secrets_module.get_secret('GAP_SECRET_KEY', default='fallback', prefer_vault=True) == 'fallback'
