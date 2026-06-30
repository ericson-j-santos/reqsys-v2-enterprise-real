"""Testes de caminhos críticos — serviço codex_governado (providers e utilitários)."""

from unittest.mock import patch

import pytest

from app.services import codex_governado as svc


def test_gerar_correlation_id_preserva_valor():
    assert svc.gerar_correlation_id('  corr-manual  ') == 'corr-manual'


def test_extrair_resposta_textual_prioriza_envelope_data():
    texto = svc._extrair_resposta_textual({'data': {'resposta': 'ok via envelope'}})
    assert texto == 'ok via envelope'


def test_extrair_resposta_textual_sem_conteudo():
    with pytest.raises(RuntimeError, match='sem conteudo'):
        svc._extrair_resposta_textual({'data': {}})


@patch('app.services.codex_governado._post_json', return_value={'response': 'ollama ok'})
def test_chamar_ollama(mock_post):
    assert svc.chamar_ollama('prompt') == 'ollama ok'
    mock_post.assert_called_once()


@patch('app.services.codex_governado._post_json', return_value={'choices': [{'message': {'content': 'openai ok'}}]})
def test_chamar_openai(mock_post, monkeypatch):
    monkeypatch.setattr(svc.settings, 'codex_openai_key', 'sk-test')
    monkeypatch.setattr(svc.settings, 'codex_openai_model', 'gpt-test')
    assert svc.chamar_openai('prompt') == 'openai ok'


@patch('app.services.codex_governado._post_json', return_value={'content': [{'text': 'claude ok'}]})
def test_chamar_claude(mock_post, monkeypatch):
    monkeypatch.setattr(svc.settings, 'codex_claude_key', 'claude-test')
    monkeypatch.setattr(svc.settings, 'codex_claude_model', 'claude-test-model')
    assert svc.chamar_claude('prompt') == 'claude ok'


def test_executar_provider_mock():
    resposta = svc.executar_provider('mock', 'prompt', 'ctx', 'entrada', 'corr-1')
    assert 'correlation_id' in resposta


def test_executar_provider_desconhecido():
    with pytest.raises(RuntimeError, match='nao suportado'):
        svc.executar_provider('invalido', 'p', 'c', 'e', 'corr')  # type: ignore[arg-type]


@patch('app.services.codex_governado.chamar_ollama', return_value='ollama via provider')
def test_executar_provider_ollama(mock_ollama):
    assert svc.executar_provider('ollama', 'p', 'c', 'e', 'corr') == 'ollama via provider'
    mock_ollama.assert_called_once_with('p')


@patch('app.services.codex_governado._post_json', return_value={'data': {'resposta': 'gateway ok'}})
def test_chamar_ollama_gateway(mock_post, monkeypatch):
    monkeypatch.setattr(svc.settings, 'codex_ollama_gateway_url', 'https://gw.example')
    monkeypatch.setattr(svc.settings, 'codex_ollama_gateway_api_key', 'gw-key')
    assert svc.chamar_ollama_gateway('prompt', 'ctx', 'entrada', 'corr-gw') == 'gateway ok'
    headers = mock_post.call_args.kwargs.get('headers') or mock_post.call_args[1].get('headers')
    assert headers['X-API-Key'] == 'gw-key'


def test_chamar_ollama_gateway_sem_url(monkeypatch):
    monkeypatch.setattr(svc.settings, 'codex_ollama_gateway_url', '')
    with pytest.raises(RuntimeError, match='GATEWAY_URL'):
        svc.chamar_ollama_gateway('p', 'c', 'e', 'corr')


def test_chamar_openai_sem_key(monkeypatch):
    monkeypatch.setattr(svc.settings, 'codex_openai_key', '')
    with pytest.raises(RuntimeError, match='OPENAI_KEY'):
        svc.chamar_openai('prompt')


def test_chamar_claude_sem_key(monkeypatch):
    monkeypatch.setattr(svc.settings, 'codex_claude_key', '')
    with pytest.raises(RuntimeError, match='CLAUDE_KEY'):
        svc.chamar_claude('prompt')


def test_publicar_reqsys_sem_endpoint(monkeypatch):
    monkeypatch.setattr(svc.settings, 'codex_reqsys_endpoint', '')
    result = svc.publicar_reqsys({'x': 1})
    assert result['publicado'] is False


@patch('app.services.codex_governado._post_json', return_value={'ok': True})
def test_publicar_reqsys_com_endpoint(mock_post, monkeypatch):
    monkeypatch.setattr(svc.settings, 'codex_reqsys_endpoint', 'https://reqsys.example/hook')
    monkeypatch.setattr(svc.settings, 'codex_reqsys_key', 'key-1')
    result = svc.publicar_reqsys({'x': 1})
    assert result['publicado'] is True
    mock_post.assert_called_once()


def test_calcular_score_confianca():
    assert svc.calcular_score_confianca('mock', bloqueado=True, reqsys_publicado=False) == 0
    assert svc.calcular_score_confianca('openai', bloqueado=False, reqsys_publicado=True) == 90
    assert svc.calcular_score_confianca('ollama_gateway', bloqueado=False, reqsys_publicado=False) == 85


def test_analisar_governado_bloqueia_conteudo_sensivel(db_session):
    resultado = svc.analisar_governado(
        provider='mock',
        contexto='contexto seguro',
        entrada='password: segredo123',
        usuario={'email': 'qa@reqsys.local'},
        correlation_id='corr-codex-block',
        publicar_no_reqsys=False,
        db=db_session,
    )

    assert resultado['bloqueado'] is True
    assert resultado['motivo'] == 'conteudo_sensivel'


def test_resumo_operacional_retorna_metricas(db_session):
    resumo = svc.resumo_operacional(db_session, limite=3)
    assert 'total' in resumo
    assert 'recentes' in resumo
    assert isinstance(resumo['recentes'], list)


def test_registrar_auditoria_sem_db_apenas_audita():
    with patch('app.services.codex_governado.auditar') as mock_auditar:
        svc.registrar_auditoria(
            None,
            correlation_id='corr-audit',
            usuario='qa@reqsys.local',
            provider='mock',
            status='ok',
            bloqueado=False,
        )
    mock_auditar.assert_called_once()


def test_registrar_auditoria_persiste_no_banco(db_session):
    svc.registrar_auditoria(
        db_session,
        correlation_id='corr-audit-db',
        usuario='qa@reqsys.local',
        provider='mock',
        status='ok',
        bloqueado=False,
        motivo='teste',
        fingerprint='fp-1',
        latencia_ms=12,
        reqsys_publicado=True,
        score_confianca=80,
    )
    resumo = svc.resumo_operacional(db_session, limite=5)
    assert resumo['total'] >= 1
