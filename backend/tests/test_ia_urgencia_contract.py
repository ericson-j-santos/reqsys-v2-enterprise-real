"""Contrato de urgência com provider simulado; não substitui o E2E em DEV."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ia import router
from app.services import gemini as gemini_svc


INVALIDAS = [
    '',
    'Não foi possível classificar.',
    'JUSTIFICATIVA: Informação insuficiente.',
    'URGENCIA: desconhecida\nJUSTIFICATIVA: Informação insuficiente.',
    'URGENCIA: alta',
    'URGENCIA: alta\nJUSTIFICATIVA:   ',
    'URGENCIA: \nJUSTIFICATIVA: Informação insuficiente.',
    'URGENCIA: alta\nURGENCIA: baixa\nJUSTIFICATIVA: Conflito.',
    'URGENCIA: alta\nURGENCIA: alta\nJUSTIFICATIVA: Duplicada.',
    'URGENCIA: alta\nJUSTIFICATIVA: Motivo.\nJUSTIFICATIVA: Outro motivo.',
    'URGENCIA: alta ou critica\nJUSTIFICATIVA: Ambígua.',
    'URGENCIA: alta\nJUSTIFICATIVA: Motivo.\nObservação fora do contrato.',
]


@pytest.mark.parametrize('resposta', INVALIDAS)
@pytest.mark.parametrize('provedor', ['gemini', 'groq'])
def test_resposta_invalida_nao_assume_urgencia_media(resposta, provedor):
    # O teste importa somente a API anterior e falha nela: DID NOT RAISE.
    with patch(
        'app.services.gemini._gerar_com_fallback',
        return_value=(resposta, provedor),
    ):
        with pytest.raises(ValueError, match='Resposta inválida da IA'):
            gemini_svc.classificar_urgencia('Título', 'Descrição', 'example-key', 'example-model')


@pytest.mark.parametrize(
    ('valor', 'esperado'),
    [('baixa', 'baixa'), ('media', 'media'), ('alta', 'alta'), ('critica', 'critica'),
     ('MÉDIA', 'media'), ('CRÍTICA', 'critica')],
)
@pytest.mark.parametrize('provedor', ['gemini', 'groq'])
def test_resposta_valida_preserva_contrato_e_normaliza(valor, esperado, provedor):
    resposta = f'  URGÊNCIA : {valor}  \n\n JUSTIFICATIVA : Impacto: analisado.  '
    with patch(
        'app.services.gemini._gerar_com_fallback',
        return_value=(resposta, provedor),
    ):
        resultado, observado = gemini_svc.classificar_urgencia(
            'Título', 'Descrição', 'example-key', 'example-model',
        )
    assert resultado.urgencia == esperado
    assert resultado.justificativa == 'Impacto: analisado.'
    assert observado == provedor


def test_resposta_invalida_nao_dispara_nova_chamada_silenciosa():
    with patch('app.services.gemini._gerar', return_value='Resposta incompleta.') as gemini:
        with patch('app.services.gemini._gerar_groq') as groq:
            with pytest.raises(ValueError, match='Resposta inválida da IA'):
                gemini_svc.classificar_urgencia(
                    'Título', 'Descrição', 'example-key', 'example-model',
                    groq_key='example-fallback-key', groq_model='example-fallback-model',
                )
    gemini.assert_called_once()
    groq.assert_not_called()


def test_fallback_por_indisponibilidade_continua_validando_urgencia():
    with patch(
        'app.services.gemini._gerar',
        side_effect=gemini_svc.GeminiIndisponivel('Provider indisponível.'),
    ):
        with patch(
            'app.services.gemini._gerar_groq',
            return_value='URGENCIA: critica\nJUSTIFICATIVA: Serviço interrompido.',
        ) as groq:
            resultado, provedor = gemini_svc.classificar_urgencia(
                'Título', 'Descrição', 'example-key', 'example-model',
                groq_key='example-fallback-key', groq_model='example-fallback-model',
            )
    assert resultado.urgencia == 'critica'
    assert provedor == 'groq'
    groq.assert_called_once()


@pytest.fixture
def ia_client():
    # Router HTTP real; somente a geração externa será simulada pelos testes.
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        yield client


def test_http_resposta_invalida_e_repeticao_nao_retornam_classificacao(ia_client):
    resposta = 'Marcador fictício que não deve aparecer no erro: private-test-marker'
    with patch('app.services.gemini._gerar_com_fallback', return_value=(resposta, 'gemini')):
        responses = [
            ia_client.post(
                '/v1/ia/classificar-urgencia',
                json={'titulo': 'Título', 'descricao': 'Descrição'},
            )
            for _ in range(2)
        ]
    for response in responses:
        assert response.status_code == 502
        payload = response.json()
        assert payload['detail']['code'] == 'IA_CLASSIFICACAO_INVALIDA'
        assert 'Revise a urgência manualmente' in payload['detail']['message']
        assert 'data' not in payload
        assert 'urgencia' not in payload
        assert 'private-test-marker' not in response.text
    assert responses[0].json() == responses[1].json()


@pytest.mark.parametrize('urgencia', ['baixa', 'media', 'alta', 'critica'])
def test_http_classificacao_valida_mantem_envelope(ia_client, urgencia):
    resposta = f'URGENCIA: {urgencia}\nJUSTIFICATIVA: Impacto avaliado.'
    with patch('app.services.gemini._gerar_com_fallback', return_value=(resposta, 'groq')):
        response = ia_client.post(
            '/v1/ia/classificar-urgencia',
            json={'titulo': 'Título', 'descricao': 'Descrição'},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['errors'] == []
    assert payload['data'] == {
        'urgencia': urgencia,
        'justificativa': 'Impacto avaliado.',
        'provedor': 'groq',
    }


def test_http_indisponibilidade_continua_503(ia_client):
    with patch(
        'app.services.gemini._gerar_com_fallback',
        side_effect=gemini_svc.GeminiIndisponivel('Provider indisponível.'),
    ):
        response = ia_client.post(
            '/v1/ia/classificar-urgencia',
            json={'titulo': 'Título', 'descricao': 'Descrição'},
        )
    assert response.status_code == 503
    assert response.json()['detail'] == 'Provider indisponível.'


def test_http_payload_invalido_nao_chama_provider(ia_client):
    with patch('app.services.gemini._gerar_com_fallback') as provider:
        response = ia_client.post('/v1/ia/classificar-urgencia', json={'titulo': 'Sem descrição'})
    assert response.status_code == 422
    provider.assert_not_called()
