"""Fallback automático de modelo quando o provider responde model_not_found / decommissioned.

Cenário real (DEV, 2026-09-10): GEMINI_MODEL=gemini-2.0-flash aposentado pelo Google e
Groq respondendo `404 model_not_found` para o modelo configurado — a IA Assistente
do formulário de requisito ficava indisponível mesmo com ambas as chaves válidas.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.services import gemini as gemini_svc
from app.services import llm_provider


def _resposta_groq_404(model: str) -> dict:
    return {'choices': [{'message': {'content': f'ok via {model}'}}]}


def _post_json_groq_com_modelo_aposentado(url, payload, headers=None, timeout=45):
    if payload['model'] == 'modelo-aposentado':
        raise requests.HTTPError(
            '404 Client Error: Not Found for url: https://api.groq.com/openai/v1/chat/completions '
            '| model_not_found The model `modelo-aposentado` does not exist or you do not have access to it.'
        )
    return _resposta_groq_404(payload['model'])


def test_groq_usa_modelo_alternativo_quando_configurado_retorna_404():
    with patch('app.services.gemini._post_json', side_effect=_post_json_groq_com_modelo_aposentado) as post:
        texto = gemini_svc._gerar_groq('key', 'modelo-aposentado', 'prompt')

    assert texto == f'ok via {gemini_svc.GROQ_MODELOS_ALTERNATIVOS[0]}'
    modelos_tentados = [call.args[1]['model'] for call in post.call_args_list]
    assert modelos_tentados == ['modelo-aposentado', gemini_svc.GROQ_MODELOS_ALTERNATIVOS[0]]


def test_groq_404_model_not_found_nao_e_classificado_como_chave_invalida():
    # Groq devolve `invalid_request_error` no corpo — a heurística de chave inválida
    # ("invalid") não pode capturar esse caso antes da checagem de modelo.
    erro = requests.HTTPError('404 Client Error | invalid_request_error model_not_found')
    with patch('app.services.gemini._post_json', side_effect=erro), pytest.raises(gemini_svc.GeminiIndisponivel) as exc:
        gemini_svc._gerar_groq('key', 'modelo-aposentado', 'prompt')

    assert 'não disponível' in str(exc.value)
    assert 'inválida' not in str(exc.value)
    assert 'GROQ_MODEL' in str(exc.value)


def test_groq_decommissioned_400_aciona_fallback_de_modelo():
    def post(url, payload, headers=None, timeout=45):
        if payload['model'] == 'llama-antigo':
            raise requests.HTTPError(
                '400 Client Error: Bad Request | model_decommissioned '
                'The model `llama-antigo` has been decommissioned'
            )
        return _resposta_groq_404(payload['model'])

    with patch('app.services.gemini._post_json', side_effect=post):
        texto = gemini_svc._gerar_groq('key', 'llama-antigo', 'prompt')
    assert texto.startswith('ok via ')


def test_gemini_usa_modelo_alternativo_quando_configurado_foi_aposentado():
    def post(url, payload, headers=None, timeout=45):
        if 'gemini-2.0-flash:' in url:
            raise requests.HTTPError('404 Client Error: Not Found | NOT_FOUND models/gemini-2.0-flash is not found')
        return {'candidates': [{'content': {'parts': [{'text': 'ok gemini alternativo'}]}}]}

    with patch('app.services.gemini._post_json', side_effect=post) as mock_post:
        texto = gemini_svc._gerar('key', 'gemini-2.0-flash', 'prompt')

    assert texto == 'ok gemini alternativo'
    urls = [call.args[0] for call in mock_post.call_args_list]
    assert 'gemini-2.0-flash:generateContent' in urls[0]
    assert f'{gemini_svc.GEMINI_MODELOS_ALTERNATIVOS[0]}:generateContent' in urls[1]


def test_modelos_candidatos_nao_repete_modelo_configurado():
    candidatos = gemini_svc._modelos_candidatos('llama-3.1-8b-instant', gemini_svc.GROQ_MODELOS_ALTERNATIVOS)
    assert candidatos[0] == 'llama-3.1-8b-instant'
    assert candidatos.count('llama-3.1-8b-instant') == 1
    assert len(candidatos) == len(gemini_svc.GROQ_MODELOS_ALTERNATIVOS)


def test_fallback_completo_gemini_aposentado_e_groq_404_mensagem_combinada():
    erro = requests.HTTPError('404 Client Error: Not Found | model_not_found')
    with patch('app.services.gemini._post_json', side_effect=erro), pytest.raises(gemini_svc.GeminiIndisponivel) as exc:
        gemini_svc._gerar_com_fallback('g-key', 'gemini-2.0-flash', 'q-key', 'llama-antigo', 'prompt')

    mensagem = str(exc.value)
    assert mensagem.startswith('Nenhum provider IA disponível')
    assert 'Gemini:' in mensagem and 'Groq:' in mensagem
    assert 'gemini-2.0-flash' in mensagem and 'llama-antigo' in mensagem


def test_fallback_completo_cenario_da_tela_novo_requisito():
    """Gemini aposentado + Groq configurado com modelo aposentado => Groq alternativo responde."""

    def post(url, payload, headers=None, timeout=45):
        if 'generativelanguage' in url:
            raise requests.HTTPError('404 Client Error: Not Found | NOT_FOUND model not found')
        if payload['model'] == 'llama-antigo':
            raise requests.HTTPError('404 Client Error: Not Found | model_not_found')
        return _resposta_groq_404(payload['model'])

    with patch('app.services.gemini._post_json', side_effect=post):
        texto, provedor = gemini_svc.resumir_requisito(
            'fluxo_auditoria_lowcode', 'descricao', 'g-key', 'gemini-2.0-flash', 'q-key', 'llama-antigo',
        )

    assert provedor == 'groq'
    assert texto.startswith('ok via ')


# ---------------------------------------------------------------------------
# llm_provider: corpo do erro HTTP precisa chegar na mensagem (antes era descartado)
# ---------------------------------------------------------------------------
def _resposta_http(status: int, corpo_json=None, texto: str = '') -> MagicMock:
    resposta = MagicMock(spec=requests.Response)
    resposta.status_code = status
    resposta.text = texto
    if corpo_json is None:
        resposta.json.side_effect = ValueError('not json')
    else:
        resposta.json.return_value = corpo_json
    http_error = requests.HTTPError(f'{status} Client Error: Not Found for url: https://api.groq.com/x', response=resposta)
    resposta.raise_for_status.side_effect = http_error
    return resposta


def test_do_post_inclui_codigo_e_mensagem_do_provider_no_erro():
    resposta = _resposta_http(404, {
        'error': {
            'message': 'The model `llama-antigo` does not exist or you do not have access to it.',
            'type': 'invalid_request_error',
            'code': 'model_not_found',
        }
    })
    with patch('app.services.llm_provider.requests.post', return_value=resposta), pytest.raises(requests.HTTPError) as exc:
        llm_provider._do_post('https://api.groq.com/x', {}, None, 5)

    mensagem = str(exc.value)
    assert '404 Client Error' in mensagem
    assert 'model_not_found' in mensagem
    assert 'does not exist' in mensagem


def test_do_post_limita_tamanho_do_corpo_do_erro():
    resposta = _resposta_http(500, None, texto='x' * 5000)
    with patch('app.services.llm_provider.requests.post', return_value=resposta), pytest.raises(requests.HTTPError) as exc:
        llm_provider._do_post('https://api.groq.com/x', {}, None, 5)
    assert len(str(exc.value)) < 500 + llm_provider._HTTP_ERROR_BODY_MAX_CHARS


def test_do_post_sem_corpo_mantem_erro_original():
    resposta = _resposta_http(502, None, texto='')
    with patch('app.services.llm_provider.requests.post', return_value=resposta), pytest.raises(requests.HTTPError) as exc:
        llm_provider._do_post('https://api.groq.com/x', {}, None, 5)
    assert str(exc.value) == '502 Client Error: Not Found for url: https://api.groq.com/x'
