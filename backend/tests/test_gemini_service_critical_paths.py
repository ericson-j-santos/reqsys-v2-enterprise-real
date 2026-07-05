"""Testes de caminhos críticos — tracker e fallback do serviço Gemini."""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from app.services import gemini as gemini_svc


def test_usage_tracker_snapshot_novo_dia(monkeypatch):
    tracker = gemini_svc._UsageTracker(limite_por_minuto=5, limite_por_dia=10)
    tracker._dia_atual = date(2020, 1, 1)
    tracker._total_dia = 9
    tracker._janela_minuto.append(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp())

    snapshot = tracker.snapshot()

    assert snapshot['req_hoje'] == 0
    assert snapshot['restante_dia'] == 10


def test_usage_tracker_limpa_eventos_antigos_da_janela():
    tracker = gemini_svc._UsageTracker(limite_por_minuto=5, limite_por_dia=10)
    tracker._dia_atual = date.today()
    tracker._janela_minuto.append(datetime.now(timezone.utc).timestamp() - 120)
    tracker.registrar()
    snapshot = tracker.snapshot()
    assert snapshot['req_ultimo_minuto'] == 1


def test_usage_tracker_registrar_novo_dia_limpa_janela():
    tracker = gemini_svc._UsageTracker(limite_por_minuto=5, limite_por_dia=10)
    tracker._dia_atual = date(2000, 1, 1)
    tracker._total_dia = 5
    tracker._janela_minuto.append(1.0)

    tracker.registrar()
    snapshot = tracker.snapshot()

    assert snapshot['req_hoje'] == 1
    assert snapshot['req_ultimo_minuto'] == 1


def test_usage_tracker_registrar_e_snapshot():
    tracker = gemini_svc._UsageTracker(limite_por_minuto=5, limite_por_dia=10)
    tracker.registrar()
    tracker.registrar()

    snapshot = tracker.snapshot()

    assert snapshot['req_hoje'] == 2
    assert snapshot['req_ultimo_minuto'] >= 1


def test_get_uso_e_get_uso_groq():
    uso_gemini = gemini_svc.get_uso()
    uso_groq = gemini_svc.get_uso_groq()
    assert 'req_hoje' in uso_gemini
    assert 'req_hoje' in uso_groq


def test_gemini_indisponivel_eh_exception():
    with pytest.raises(gemini_svc.GeminiIndisponivel):
        raise gemini_svc.GeminiIndisponivel('sem provider')


@patch('app.services.gemini._post_json', side_effect=Exception('429 rate limit exceeded'))
def test_gerar_quota_esgotada(mock_post):
    with pytest.raises(gemini_svc.GeminiIndisponivel, match='Quota Gemini'):
        gemini_svc._gerar('key', 'gemini-2.0-flash', 'prompt')


@patch('app.services.gemini._post_json', side_effect=Exception('400 invalid api_key'))
def test_gerar_api_key_invalida(mock_post):
    with pytest.raises(gemini_svc.GeminiIndisponivel, match='inválida'):
        gemini_svc._gerar('key', 'gemini-2.0-flash', 'prompt')


@patch('app.services.gemini._post_json', side_effect=Exception('404 model not found'))
def test_gerar_modelo_nao_encontrado(mock_post):
    with pytest.raises(gemini_svc.GeminiIndisponivel, match='não disponível'):
        gemini_svc._gerar('key', 'bad-model', 'prompt')


@patch('app.services.gemini._post_json', side_effect=Exception('falha interna xyz'))
def test_gerar_erro_inesperado(mock_post):
    with pytest.raises(gemini_svc.GeminiIndisponivel, match='indisponível'):
        gemini_svc._gerar('key', 'gemini-2.0-flash', 'prompt')


@patch(
    'app.services.gemini._post_json',
    return_value={'candidates': [{'content': {'parts': [{'text': '  resposta ok  '}]}}]},
)
def test_gerar_sucesso_registra_uso(mock_post):
    texto = gemini_svc._gerar('key', 'gemini-2.0-flash', 'prompt')
    assert texto == 'resposta ok'
    payload = mock_post.call_args.args[1]
    headers = mock_post.call_args.kwargs['headers']
    assert payload['model'] == 'gemini-2.0-flash'
    assert headers['x-goog-api-key'] == 'key'


@patch('app.services.gemini._post_json', side_effect=Exception('429 rate_limit_exceeded'))
def test_gerar_groq_quota_esgotada(mock_post):
    with pytest.raises(gemini_svc.GeminiIndisponivel, match='Quota Groq'):
        gemini_svc._gerar_groq('key', 'llama', 'prompt')


@patch('app.services.gemini._post_json', side_effect=Exception('401 invalid api key'))
def test_gerar_groq_api_key_invalida(mock_post):
    with pytest.raises(gemini_svc.GeminiIndisponivel, match='inválida'):
        gemini_svc._gerar_groq('key', 'llama', 'prompt')


@patch('app.services.gemini._post_json', side_effect=Exception('erro desconhecido'))
def test_gerar_groq_erro_inesperado(mock_post):
    with pytest.raises(gemini_svc.GeminiIndisponivel, match='indisponível'):
        gemini_svc._gerar_groq('key', 'llama', 'prompt')


@patch(
    'app.services.gemini._post_json',
    return_value={'choices': [{'message': {'content': '  groq ok  '}}]},
)
def test_gerar_groq_sucesso(mock_post):
    texto = gemini_svc._gerar_groq('key', 'llama', 'prompt')
    assert texto == 'groq ok'
    payload = mock_post.call_args.args[1]
    headers = mock_post.call_args.kwargs['headers']
    assert payload['model'] == 'llama'
    assert headers['Authorization'] == 'Bearer key'


def test_classificar_urgencia_normaliza_acentos():
    resposta = 'URGENCIA: crítica\nJUSTIFICATIVA: Risco alto.'
    with patch('app.services.gemini._gerar_com_fallback', return_value=(resposta, 'gemini')):
        classificacao, _ = gemini_svc.classificar_urgencia('t', 'd', 'k', 'model')
    assert classificacao.urgencia == 'critica'
    assert classificacao.justificativa == 'Risco alto.'
