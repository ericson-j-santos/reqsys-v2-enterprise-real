"""Gaps de cobertura — prontidao, estatisticas, hub_lowcode, github_redmine, otel (fase 10)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.core.otel as otel_module
from app.db import SessionLocal
from app.models.requisito import Requisito
from app.schemas.processos import ContextoAntecipacao, TipoProcesso, UsuarioExecucao
from app.services import hub_lowcode as hub_svc
from app.services import github_redmine as gr
from app.services.estatisticas import _estado_percentual, _normalizar_percentual, _tem_bdd, _tem_lacuna, gerar_indicadores_estatisticos
from app.services.prontidao import antecipar_validacoes


def _contexto(**overrides):
    base = {
        'tipo_processo': TipoProcesso.DEMANDA,
        'acao': 'iniciar',
        'usuario': UsuarioExecucao(id='u1', perfil='admin', escopos=['demanda:iniciar']),
        'dados': {
            'titulo': 'Titulo',
            'descricao': 'Descricao',
            'responsavel': 'time',
            'prioridade': 'alta',
            'evidencias': [{'tipo': 'doc', 'referencia': 'DOC-1'}],
            'criterio_aceite': 'Aceite definido',
            'valor_negocio': 'Alto',
        },
        'correlation_id': 'corr-phase10',
    }
    base.update(overrides)
    return ContextoAntecipacao(**base)


def test_prontidao_demanda_sem_evidencia_bloqueia():
    dados = _contexto().dados.copy()
    dados.pop('evidencias')
    resultado = antecipar_validacoes(_contexto(dados=dados))
    assert resultado.apto_para_iniciar is False
    assert any(b.codigo == 'EVIDENCIA_OBRIGATORIA_AUSENTE' for b in resultado.bloqueios)


def test_prontidao_demanda_completa_aprovada():
    resultado = antecipar_validacoes(_contexto())
    assert resultado.status_validacao == 'aprovado'
    assert not resultado.bloqueios
    assert not resultado.alertas


def test_estatisticas_helpers_percentual_e_estado():
    assert _normalizar_percentual(0, 0) == 0
    assert _normalizar_percentual(1, 4) == 25
    assert _estado_percentual(85) == 'adequado'
    assert _estado_percentual(50) == 'atencao'
    assert _estado_percentual(10) == 'critico'


def test_estatisticas_tem_bdd_e_lacuna():
    com_bdd = Requisito(
        codigo='REQ-BDD-1', titulo='Fluxo', descricao='Dado contexto Quando acao Entao resultado',
        status='aprovado', urgencia='alta', area='QA', sistema='ReqSys', solicitante='qa@test',
    )
    com_lacuna = Requisito(
        codigo='REQ-LAC-1', titulo='Pendente TBD', descricao='A definir',
        status='pendente', urgencia='media', area='QA', sistema='ReqSys', solicitante='qa@test',
    )
    assert _tem_bdd(com_bdd) is True
    assert _tem_lacuna(com_lacuna) is True


@patch('app.services.estatisticas.resumo_fontes_externas', return_value={'autorizadas_validas': 0, 'total': 0})
@patch('app.services.estatisticas.listar_fontes_externas', return_value=[])
def test_gerar_indicadores_estatisticos_com_db_vazia(_fontes, _resumo):
    db = SessionLocal()
    try:
        indicadores = gerar_indicadores_estatisticos(db, tendencias={})
        assert isinstance(indicadores, list)
        assert len(indicadores) >= 1
    finally:
        db.close()


@patch('app.services.github_redmine.request.urlopen')
def test_github_redmine_request_json_corpo_vazio(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b''
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    assert gr._request_json('GET', 'https://api.github.com/repos/o/r/issues') == {}


def test_hub_lowcode_try_json_referencia_circular():
    circular: list = []
    circular.append(circular)
    resultado = hub_svc._try_json(circular)
    assert isinstance(resultado, str)


def test_hub_lowcode_salvar_log_degrada_em_excecao():
    db = SessionLocal()
    try:
        with patch.object(db, 'commit', side_effect=RuntimeError('db lock')):
            hub_svc.salvar_log_integracao(db, tipo='planner', status='sucesso', correlation_id='c-err')
    finally:
        db.close()


def test_hub_lowcode_listar_historico_degrada_em_excecao():
    db = SessionLocal()
    try:
        with patch.object(db, 'execute', side_effect=RuntimeError('db offline')):
            historico = hub_svc.listar_historico_integracoes(db, tipo='planner')
        assert historico['eventos'] == []
        assert 'db offline' in historico['erro']
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_hub_lowcode_teams_webhook_erro_generico(mock_client_cls):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=RuntimeError('teams offline'))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = asyncio.run(hub_svc.testar_teams_webhook('https://example.com/teams'))

    assert resultado['ok'] is False
    assert 'teams offline' in resultado['erro']


def test_otel_configura_fallback_console_sem_otlp(monkeypatch):
    import builtins

    monkeypatch.setattr(otel_module, '_otel_configured', False)
    monkeypatch.setattr(otel_module.settings, 'otel_enabled', True)
    monkeypatch.setattr(otel_module.settings, 'otel_exporter_endpoint', 'http://otel.local/v1/traces')

    real_import = builtins.__import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'opentelemetry.exporter.otlp.proto.http.trace_exporter':
            raise ImportError('sem otlp')
        return real_import(name, globals, locals, fromlist, level)

    with patch('builtins.__import__', side_effect=mock_import):
        assert otel_module.configurar_opentelemetry(MagicMock()) is True

    monkeypatch.setattr(otel_module, '_otel_configured', False)


def test_otel_anotar_span_ignora_quando_nao_gravando(monkeypatch):
    monkeypatch.setattr(otel_module, '_otel_configured', True)
    span = MagicMock()
    span.is_recording.return_value = False
    fake_trace = MagicMock()
    fake_trace.get_current_span.return_value = span

    with patch('opentelemetry.trace', fake_trace, create=True):
        otel_module.anotar_span_correlation()

    span.set_attribute.assert_not_called()
