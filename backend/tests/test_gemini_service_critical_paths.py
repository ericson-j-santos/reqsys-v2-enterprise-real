"""Testes de caminhos críticos — tracker e fallback do serviço Gemini."""

import sys
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services import gemini as gemini_svc


def _mock_genai_module():
    mock_genai = MagicMock()
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    return mock_genai, mock_model


def _mock_groq_module():
    mock_groq = MagicMock()
    mock_client = MagicMock()
    mock_groq.Groq.return_value = mock_client
    return mock_groq, mock_client


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


def test_gerar_quota_esgotada():
    mock_genai, mock_model = _mock_genai_module()
    mock_model.generate_content.side_effect = Exception('429 rate limit exceeded')
    with patch.dict(sys.modules, {'google.generativeai': mock_genai}):
        with pytest.raises(gemini_svc.GeminiIndisponivel, match='Quota Gemini'):
            gemini_svc._gerar('key', 'gemini-2.0-flash', 'prompt')


def test_gerar_api_key_invalida():
    mock_genai, mock_model = _mock_genai_module()
    mock_model.generate_content.side_effect = Exception('400 invalid api_key')
    with patch.dict(sys.modules, {'google.generativeai': mock_genai}):
        with pytest.raises(gemini_svc.GeminiIndisponivel, match='inválida'):
            gemini_svc._gerar('key', 'gemini-2.0-flash', 'prompt')


def test_gerar_modelo_nao_encontrado():
    mock_genai, mock_model = _mock_genai_module()
    mock_model.generate_content.side_effect = Exception('404 model not found')
    with patch.dict(sys.modules, {'google.generativeai': mock_genai}):
        with pytest.raises(gemini_svc.GeminiIndisponivel, match='não disponível'):
            gemini_svc._gerar('key', 'bad-model', 'prompt')


def test_gerar_erro_inesperado():
    mock_genai, mock_model = _mock_genai_module()
    mock_model.generate_content.side_effect = Exception('falha interna xyz')
    with patch.dict(sys.modules, {'google.generativeai': mock_genai}):
        with pytest.raises(gemini_svc.GeminiIndisponivel, match='indisponível'):
            gemini_svc._gerar('key', 'gemini-2.0-flash', 'prompt')


def test_gerar_sucesso_registra_uso():
    mock_genai, mock_model = _mock_genai_module()
    mock_model.generate_content.return_value = MagicMock(text='  resposta ok  ')
    with patch.dict(sys.modules, {'google.generativeai': mock_genai}):
        texto = gemini_svc._gerar('key', 'gemini-2.0-flash', 'prompt')
    assert texto == 'resposta ok'


def test_gerar_groq_quota_esgotada():
    mock_groq, mock_client = _mock_groq_module()
    mock_client.chat.completions.create.side_effect = Exception('429 rate_limit_exceeded')
    with patch.dict(sys.modules, {'groq': mock_groq}):
        with pytest.raises(gemini_svc.GeminiIndisponivel, match='Quota Groq'):
            gemini_svc._gerar_groq('key', 'llama', 'prompt')


def test_gerar_groq_api_key_invalida():
    mock_groq, mock_client = _mock_groq_module()
    mock_client.chat.completions.create.side_effect = Exception('401 invalid api key')
    with patch.dict(sys.modules, {'groq': mock_groq}):
        with pytest.raises(gemini_svc.GeminiIndisponivel, match='inválida'):
            gemini_svc._gerar_groq('key', 'llama', 'prompt')


def test_gerar_groq_erro_inesperado():
    mock_groq, mock_client = _mock_groq_module()
    mock_client.chat.completions.create.side_effect = Exception('erro desconhecido')
    with patch.dict(sys.modules, {'groq': mock_groq}):
        with pytest.raises(gemini_svc.GeminiIndisponivel, match='indisponível'):
            gemini_svc._gerar_groq('key', 'llama', 'prompt')


def test_gerar_groq_sucesso():
    mock_groq, mock_client = _mock_groq_module()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='  groq ok  '))]
    )
    with patch.dict(sys.modules, {'groq': mock_groq}):
        texto = gemini_svc._gerar_groq('key', 'llama', 'prompt')
    assert texto == 'groq ok'


def test_classificar_urgencia_normaliza_acentos():
    resposta = 'URGENCIA: crítica\nJUSTIFICATIVA: Risco alto.'
    with patch('app.services.gemini._gerar_com_fallback', return_value=(resposta, 'gemini')):
        classificacao, _ = gemini_svc.classificar_urgencia('t', 'd', 'k', 'model')
    assert classificacao.urgencia == 'critica'
    assert classificacao.justificativa == 'Risco alto.'
