"""Cobertura fase 7 — ia, ai_quality, prontidao, secrets, agents, otel, hub_lowcode."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core import secrets as secrets_module
from app.main import app
from app.schemas.processos import ContextoAntecipacao, TipoProcesso, UsuarioExecucao
from app.services import hub_lowcode as svc
from app.services.ai_quality import calcular_resumo_qualidade_ia
from app.services.prontidao import antecipar_validacoes

client = TestClient(app)


def _contexto_prontidao(**overrides):
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
        'correlation_id': 'corr-phase7',
    }
    base.update(overrides)
    return ContextoAntecipacao(**base)


def _db_ai_quality(cobertura_count: int, incidentes_count: int):
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value = query
    query.count.side_effect = [cobertura_count, incidentes_count]
    db.query.return_value = query
    return db


@patch('app.services.ai_quality.calcular_metricas_requisitos')
def test_ai_quality_status_critico_e_recomendacoes(mock_metricas):
    mock_metricas.return_value = {
        'total': 20,
        'aprovados': 0,
        'em_analise': 0,
        'pendentes': 20,
    }
    resumo = calcular_resumo_qualidade_ia(_db_ai_quality(cobertura_count=0, incidentes_count=3))

    assert resumo['status'] == 'critico'
    textos = ' '.join(resumo['recomendacoes'])
    assert 'cobertura' in textos.lower() or 'detalhamento' in textos.lower()
    assert 'incidentes' in textos.lower() or 'seguranca' in textos.lower()
    assert 'pendencias' in textos.lower() or 'consistencia' in textos.lower()


@patch('app.services.ai_quality.calcular_metricas_requisitos')
def test_ai_quality_status_atencao(mock_metricas):
    mock_metricas.return_value = {
        'total': 10,
        'aprovados': 4,
        'em_analise': 2,
        'pendentes': 4,
    }
    resumo = calcular_resumo_qualidade_ia(_db_ai_quality(cobertura_count=2, incidentes_count=1))

    assert resumo['status'] in {'atencao', 'estavel', 'critico'}


@patch('app.services.ai_quality.calcular_metricas_requisitos')
def test_ai_quality_status_excelente_e_manutencao(mock_metricas):
    mock_metricas.return_value = {
        'total': 5,
        'aprovados': 5,
        'em_analise': 0,
        'pendentes': 0,
    }
    resumo = calcular_resumo_qualidade_ia(_db_ai_quality(cobertura_count=5, incidentes_count=0))

    assert resumo['status'] in {'excelente', 'estavel'}
    assert any('monitoramento' in item.lower() for item in resumo['recomendacoes'])


def test_prontidao_demanda_sem_evidencia_bloqueia():
    dados = _contexto_prontidao().dados.copy()
    dados.pop('evidencias')
    resultado = antecipar_validacoes(_contexto_prontidao(dados=dados))

    assert resultado.apto_para_iniciar is False
    assert any(b.codigo == 'EVIDENCIA_OBRIGATORIA_AUSENTE' for b in resultado.bloqueios)


def test_prontidao_demanda_sem_valor_negocio_alerta():
    dados = _contexto_prontidao().dados.copy()
    dados.pop('valor_negocio')
    resultado = antecipar_validacoes(_contexto_prontidao(dados=dados))

    assert resultado.apto_para_iniciar is True
    assert resultado.status_validacao == 'aprovado_com_alerta'
    assert any(a.codigo == 'VALOR_NEGOCIO_AUSENTE' for a in resultado.alertas)


def test_prontidao_demanda_completa_aprovada():
    resultado = antecipar_validacoes(_contexto_prontidao())

    assert resultado.apto_para_iniciar is True
    assert resultado.status_validacao == 'aprovado'
    assert not resultado.bloqueios
    assert not resultado.alertas


def test_ia_status_sem_chaves_expoe_avisos_e_passos():
    with patch('app.api.ia.settings') as mock_settings:
        mock_settings.gemini_api_key = ''
        mock_settings.gemini_model = 'gemini-2.0-flash'
        mock_settings.groq_api_key = ''
        mock_settings.groq_model = 'llama-3.3-70b-versatile'
        resp = client.get('/v1/ia/status')

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['configurada'] is False
    assert data['fallback_ativo'] is False
    assert len(data['avisos']) == 2
    assert len(data['passos_pendentes']) == 2
    assert data['aviso'] is not None


def test_ia_classificar_retorna_503_quando_indisponivel():
    from app.services.gemini import GeminiIndisponivel

    with patch('app.api.ia.classificar_urgencia', side_effect=GeminiIndisponivel('offline')), \
         patch('app.api.ia.settings') as mock_settings:
        mock_settings.gemini_api_key = 'fake'
        mock_settings.gemini_model = 'gemini-2.0-flash'
        mock_settings.groq_api_key = ''
        mock_settings.groq_model = 'llama-3.3-70b-versatile'
        resp = client.post(
            '/v1/ia/classificar-urgencia',
            json={'titulo': 'Bug', 'descricao': 'Falha critica'},
        )

    assert resp.status_code == 503


def test_agents_orchestrator_health_e_coordinators():
    health = client.get('/v1/agents/orchestrator/health')
    assert health.status_code == 200
    health_data = health.json()['data']
    assert health_data['status'] == 'ok'
    assert health_data['service'] == 'reqsys-orchestrator'

    coords = client.get('/v1/agents/orchestrator/coordinators')
    assert coords.status_code == 200
    coords_data = coords.json()['data']
    assert coords_data['total'] >= 1
    assert isinstance(coords_data['coordinators'], list)


class _FakeKeyringExc:
    def __init__(self):
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        if username == 'RAISE':
            raise RuntimeError('keyring indisponivel')
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if username == 'RAISE':
            raise RuntimeError('delete falhou')
        self._store.pop((service, username), None)


def test_secrets_prefer_vault_retorna_default_quando_ausente(monkeypatch):
    fk = _FakeKeyringExc()
    monkeypatch.setattr(secrets_module, 'keyring', fk)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)
    monkeypatch.setattr(secrets_module, '_CRYPTO_OK', True)
    monkeypatch.delenv('PREF_VAULT_KEY', raising=False)

    assert secrets_module.get_secret('PREF_VAULT_KEY', default='fallback', prefer_vault=True) == 'fallback'


def test_secrets_delete_secret_retorna_false_em_excecao(monkeypatch):
    fk = _FakeKeyringExc()
    fk.set_password('svc', 'RAISE', 'valor')
    monkeypatch.setattr(secrets_module, 'keyring', fk)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)

    assert secrets_module.delete_secret_from_vault('RAISE', service_name='svc') is False


def test_secrets_vault_initialized_retorna_false_em_excecao(monkeypatch):
    fk = _FakeKeyringExc()
    monkeypatch.setattr(secrets_module, 'keyring', fk)
    monkeypatch.setattr(secrets_module, '_KEYRING_OK', True)

    assert secrets_module.vault_initialized(service_name='svc') is False


def test_otel_configura_com_fallback_console_quando_otlp_indisponivel(monkeypatch):
    import builtins

    import app.core.otel as otel_module

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


def test_otel_anotar_span_ignora_span_nao_gravando(monkeypatch):
    import app.core.otel as otel_module

    monkeypatch.setattr(otel_module, '_otel_configured', True)
    span = MagicMock()
    span.is_recording.return_value = False
    fake_trace = MagicMock()
    fake_trace.get_current_span.return_value = span

    with patch('opentelemetry.trace', fake_trace, create=True):
        otel_module.anotar_span_correlation()

    span.set_attribute.assert_not_called()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_publicar_tarefas_planner_gera_correlation_id_e_erro_generico(mock_client_cls):
    import asyncio
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        svc.salvar_planner_webhook_config(db, webhook_url='https://example.com/planner-hook')
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=RuntimeError('rede indisponivel'))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resultado = asyncio.run(
            svc.publicar_tarefas_planner(
                db,
                tarefas_texto='Tarefa|Dev|2026-06-28|Backlog|Alta|Desc',
                autor='tester',
            )
        )

        assert resultado['ok'] is False
        assert 'rede indisponivel' in resultado['erro']
        assert resultado['correlation_id']
    finally:
        db.close()


def test_try_json_fallback_quando_serializacao_falha():
    circular: list = []
    circular.append(circular)
    resultado = svc._try_json(circular)
    assert isinstance(resultado, str)
    assert len(resultado) > 0


def test_salvar_log_integracao_degrada_em_excecao():
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        with patch.object(db, 'commit', side_effect=RuntimeError('db lock')):
            svc.salvar_log_integracao(db, tipo='planner', status='sucesso', correlation_id='corr-erro-log')
    finally:
        db.close()


def test_listar_historico_integracoes_degrada_em_excecao():
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        with patch.object(db, 'execute', side_effect=RuntimeError('db offline')):
            historico = svc.listar_historico_integracoes(db, tipo='planner')
        assert historico['eventos'] == []
        assert 'db offline' in historico['erro']
    finally:
        db.close()


@patch('app.services.hub_lowcode.httpx.AsyncClient')
def test_testar_teams_webhook_erro_generico(mock_client_cls):
    import asyncio

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=RuntimeError('teams offline'))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    resultado = asyncio.run(svc.testar_teams_webhook('https://example.com/teams'))

    assert resultado['ok'] is False
    assert 'teams offline' in resultado['erro']
