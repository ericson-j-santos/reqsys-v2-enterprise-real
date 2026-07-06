from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.govbi_ai_health import montar_govbi_ai_health
from app.services.llm_telemetry import (
    obter_snapshot_telemetry_llm,
    registrar_evento_llm,
    resetar_telemetry_llm,
)

client = TestClient(app)


@pytest.fixture(scope='module')
def auth_headers():
    resp = client.post('/v1/auth/login', json={'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com'})
    token = resp.json()['data']['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_telemetry_nao_expõe_prompt_resposta_ou_chave():
    resetar_telemetry_llm()
    registrar_evento_llm('gemini', 'sucesso')
    registrar_evento_llm('gemini', 'falha', 'quota_esgotada')

    snapshot = obter_snapshot_telemetry_llm()

    assert snapshot['gemini']['total_requisicoes'] == 2
    assert snapshot['gemini']['sucessos'] == 1
    assert snapshot['gemini']['falhas'] == 1
    assert snapshot['gemini']['ultimo_tipo_erro'] == 'quota_esgotada'
    assert 'prompt' not in snapshot['gemini']
    assert 'resposta' not in snapshot['gemini']
    assert 'api_key' not in snapshot['gemini']


def test_montar_govbi_ai_health_verde_com_gemini_e_groq():
    payload = montar_govbi_ai_health(
        gemini_configurado=True,
        gemini_modelo='gemini-3.5-flash',
        gemini_cota={'restante_dia': 1500},
        groq_configurado=True,
        groq_modelo='llama-3.3-70b-versatile',
        groq_cota={'restante_dia': 14400},
        telemetry={'gemini': {'total_requisicoes': 1}},
    )

    assert payload['status_geral'] == 'verde'
    assert payload['gemini_gratuito_configurado'] is True
    assert payload['fallback_ativo'] is True
    assert payload['seguranca']['sem_chaves_expostas'] is True
    assert payload['percentual_operacional_estimado'] == 100


def test_montar_govbi_ai_health_vermelho_sem_provider():
    payload = montar_govbi_ai_health(
        gemini_configurado=False,
        gemini_modelo='gemini-3.5-flash',
        gemini_cota={'restante_dia': 0},
        groq_configurado=False,
        groq_modelo='llama-3.3-70b-versatile',
        groq_cota={'restante_dia': 0},
        telemetry={},
    )

    assert payload['status_geral'] == 'vermelho'
    assert payload['fallback_ativo'] is False
    assert payload['percentual_operacional_estimado'] == 45
    assert len(payload['passos_pendentes']) >= 2


def test_endpoint_govbi_health_retorna_status_operacional(auth_headers):
    with patch('app.api.ia.settings') as mock_settings:
        mock_settings.gemini_api_key = 'fake-gemini'
        mock_settings.gemini_model = 'gemini-3.5-flash'
        mock_settings.groq_api_key = 'fake-groq'
        mock_settings.groq_model = 'llama-3.3-70b-versatile'

        resp = client.get('/v1/ia/govbi/health', headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['produto'] == 'GovBI IA / ReqSys'
    assert data['status_geral'] == 'verde'
    assert data['provedores']['gemini']['configurado'] is True
    assert data['provedores']['groq']['configurado'] is True
    assert 'GET /v1/ia/status' in data['smoke_tests_recomendados']


def test_status_ia_inclui_govbi_health_e_telemetry(auth_headers):
    resp = client.get('/v1/ia/status', headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()['data']
    assert 'govbi_health' in data
    assert 'telemetry' in data
    assert data['govbi_health']['produto'] == 'GovBI IA / ReqSys'
