"""Testes da porta comum de LLM."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.services.llm_provider import (
    LLMGateway,
    _post_json,
    extrair_resposta_gemini,
    extrair_resposta_textual,
    reset_circuit_breakers,
)


@pytest.fixture(autouse=True)
def _circuit_breakers_isolados():
    reset_circuit_breakers()
    yield
    reset_circuit_breakers()


def test_extrair_resposta_textual_envelope_data():
    assert extrair_resposta_textual({'data': {'answer': 'ok'}}) == 'ok'


def test_extrair_resposta_gemini_generate_content():
    payload = {'candidates': [{'content': {'parts': [{'text': 'gemini ok'}]}}]}
    assert extrair_resposta_gemini(payload) == 'gemini ok'


def test_extrair_resposta_gemini_sem_conteudo():
    with pytest.raises(RuntimeError, match='Gemini sem conteudo'):
        extrair_resposta_gemini({'candidates': []})


def test_gateway_openai_monta_headers_e_payload():
    chamadas = []

    def fake_post(url, payload, headers=None, timeout=45):
        chamadas.append((url, payload, headers, timeout))
        return {'choices': [{'message': {'content': 'openai ok'}}]}

    gateway = LLMGateway(post_json=fake_post)
    texto = gateway.gerar_openai(
        api_key='sk-test',
        model='gpt-test',
        prompt='prompt',
        system_prompt='sistema',
    )

    assert texto == 'openai ok'
    assert chamadas[0][0] == 'https://api.openai.com/v1/chat/completions'
    assert chamadas[0][1]['model'] == 'gpt-test'
    assert chamadas[0][2]['Authorization'] == 'Bearer sk-test'


def test_gateway_gemini_monta_payload_padrao():
    chamadas = []

    def fake_post(url, payload, headers=None, timeout=45):
        chamadas.append((url, payload, headers, timeout))
        return {'output_text': 'gemini ok'}

    gateway = LLMGateway(post_json=fake_post)
    texto = gateway.gerar_gemini(
        api_key='AIza-test',
        model='gemini-test',
        prompt='prompt',
        system_prompt='sistema',
    )

    assert texto == 'gemini ok'
    assert chamadas[0][0] == 'https://generativelanguage.googleapis.com/v1beta/interactions'
    assert chamadas[0][1]['model'] == 'gemini-test'
    assert chamadas[0][1]['system_instruction'] == 'sistema'
    assert chamadas[0][2]['x-goog-api-key'] == 'AIza-test'


def _fake_response(payload):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


def test_post_json_tenta_novamente_apos_falha_transitoria_de_rede():
    chamadas = {'n': 0}
    sonos = []

    def fake_post(url, json, headers, timeout):
        chamadas['n'] += 1
        if chamadas['n'] < 3:
            raise requests.ConnectionError('timeout de rede')
        return _fake_response({'output_text': 'ok'})

    with patch('app.services.llm_provider.requests.post', side_effect=fake_post):
        resultado = _post_json('https://api.openai.com/v1/chat/completions', {}, sleep=sonos.append)

    assert resultado == {'output_text': 'ok'}
    assert chamadas['n'] == 3
    assert len(sonos) == 2


def test_post_json_nao_retenta_erro_http_definitivo():
    chamadas = {'n': 0}

    def fake_post(url, json, headers, timeout):
        chamadas['n'] += 1
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError('401 Unauthorized')
        return resp

    with patch('app.services.llm_provider.requests.post', side_effect=fake_post):
        with pytest.raises(requests.HTTPError):
            _post_json('https://api.openai.com/v1/chat/completions', {}, sleep=lambda _s: None)

    assert chamadas['n'] == 1


def test_post_json_circuito_abre_por_host_e_nao_afeta_outros_providers():
    def fake_post_falha(url, json, headers, timeout):
        raise requests.ConnectionError('openai fora do ar')

    with patch('app.services.llm_provider.requests.post', side_effect=fake_post_falha):
        for _ in range(3):
            with pytest.raises(requests.ConnectionError):
                _post_json('https://api.openai.com/v1/chat/completions', {}, sleep=lambda _s: None, max_retries=1)

        with pytest.raises(requests.ConnectionError, match="Circuito 'llm_api.openai.com' aberto"):
            _post_json('https://api.openai.com/v1/chat/completions', {}, sleep=lambda _s: None)

    # Outro provider (host diferente) nao deve ser afetado pelo circuito da OpenAI.
    with patch('app.services.llm_provider.requests.post', side_effect=lambda *a, **k: _fake_response({'output_text': 'groq ok'})):
        resultado = _post_json('https://api.groq.com/openai/v1/chat/completions', {}, sleep=lambda _s: None)

    assert resultado == {'output_text': 'groq ok'}
