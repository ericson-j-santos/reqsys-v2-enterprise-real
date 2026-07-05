"""Testes da porta comum de LLM."""

import pytest

from app.services.llm_provider import LLMGateway, extrair_resposta_gemini, extrair_resposta_textual


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
