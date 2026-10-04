from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.govbi_ai_health import montar_govbi_ai_health
from app.services.govbi_ai_runtime_probes import executar_runtime_probes_govbi
from app.services.llm_telemetry import (
    compactar_telemetry_llm,
    obter_snapshot_telemetry_llm,
    obter_telemetry_persistida_llm,
    registrar_evento_llm,
    resetar_telemetry_llm,
)

client = TestClient(app)


@pytest.fixture(scope='module')
def auth_headers():
    resp = client.post('/v1/auth/login', json={'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com'})
    token = resp.json()['data']['access_token']
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture(autouse=True)
def telemetry_store_tmp(monkeypatch, tmp_path):
    monkeypatch.setenv('REQSYS_LLM_TELEMETRY_STORE_PATH', str(tmp_path / 'llm-telemetry.jsonl'))
    resetar_telemetry_llm()
    yield
    resetar_telemetry_llm()


def test_telemetry_nao_expõe_prompt_resposta_ou_chave():
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


def test_telemetry_persistida_jsonl_sem_payload_sensivel():
    registrar_evento_llm('gemini', 'sucesso')
    registrar_evento_llm('groq', 'fallback_acionado')

    persistida = obter_telemetry_persistida_llm()

    assert persistida['store']['tipo'] == 'jsonl_append_only'
    assert persistida['store']['existe'] is True
    assert persistida['total_eventos'] == 2
    assert persistida['seguranca']['sem_prompt'] is True
    assert persistida['seguranca']['sem_resposta'] is True
    assert persistida['seguranca']['sem_chaves'] is True
    assert persistida['provedores']['gemini']['sucessos'] == 1
    assert persistida['provedores']['groq']['fallback_acionado'] == 1


def test_compactar_telemetry_llm_preserva_eventos_recentes():
    registrar_evento_llm('gemini', 'sucesso')

    resultado = compactar_telemetry_llm()

    assert resultado['eventos_antes'] == 1
    assert resultado['eventos_retidos'] == 1
    assert resultado['eventos_removidos'] == 0


def test_montar_govbi_ai_health_verde_com_gemini_groq_persistencia_e_probe():
    payload = montar_govbi_ai_health(
        gemini_configurado=True,
        gemini_modelo='gemini-3.5-flash',
        gemini_cota={'restante_dia': 1500},
        groq_configurado=True,
        groq_modelo='llama-3.3-70b-versatile',
        groq_cota={'restante_dia': 14400},
        telemetry={'gemini': {'total_requisicoes': 1}},
        telemetry_persistida={'store': {'existe': True}},
        ultimo_probe={'status_geral': 'verde'},
    )

    assert payload['status_geral'] == 'verde'
    assert payload['gemini_gratuito_configurado'] is True
    assert payload['fallback_ativo'] is True
    assert payload['seguranca']['sem_chaves_expostas'] is True
    assert payload['percentual_operacional_estimado'] == 100
    assert 'telemetry_persistida' in payload
    assert 'ultimo_probe' in payload


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


def test_runtime_probe_sem_provider_nao_expoe_payload():
    payload = executar_runtime_probes_govbi(
        gemini_api_key='',
        gemini_model='gemini-3.5-flash',
        groq_api_key='',
        groq_model='llama-3.3-70b-versatile',
    )

    assert payload['status_geral'] == 'amarelo'
    assert payload['resumo']['ignorados'] == 2
    assert payload['seguranca']['sem_chave_exposta'] is True
    assert all('prompt' not in probe for probe in payload['probes'])


def test_runtime_probe_com_executor_mockado_retorna_sucesso_sem_resposta_modelo():
    def executor(**kwargs):
        return 'resposta omitida', 'gemini'

    payload = executar_runtime_probes_govbi(
        gemini_api_key='fake-gemini',
        gemini_model='gemini-3.5-flash',
        groq_api_key='fake-groq',
        groq_model='llama-3.3-70b-versatile',
        executor=executor,
    )

    assert payload['status_geral'] == 'verde'
    assert payload['resumo']['sucessos'] == 1
    assert payload['probes'][0]['provider'] == 'gemini'
    assert payload['probes'][0]['status'] == 'success'
    assert 'resposta omitida' not in str(payload)


def test_endpoint_govbi_health_retorna_status_operacional(auth_headers):
    registrar_evento_llm('gemini', 'sucesso')
    with patch('app.api.ia.settings') as mock_settings:
        mock_settings.gemini_api_key = 'fake-gemini'
        mock_settings.gemini_model = 'gemini-3.5-flash'
        mock_settings.groq_api_key = 'fake-groq'
        mock_settings.groq_model = 'llama-3.3-70b-versatile'

        resp = client.get('/v1/ia/govbi/health', headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['produto'] == 'GovBI IA / ReqSys'
    assert data['provedores']['gemini']['configurado'] is True
    assert data['provedores']['groq']['configurado'] is True
    assert 'GET /v1/ia/govbi/telemetry' in data['smoke_tests_recomendados']
    assert 'POST /v1/ia/govbi/probes' in data['smoke_tests_recomendados']


def test_endpoint_govbi_telemetry_retorna_memoria_e_persistencia(auth_headers):
    registrar_evento_llm('gemini', 'sucesso')

    resp = client.get('/v1/ia/govbi/telemetry', headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()['data']
    assert 'memoria' in data
    assert 'persistida' in data
    assert data['persistida']['total_eventos'] == 1


def test_endpoint_govbi_probes_sem_provider_retorna_skipped(auth_headers):
    with patch('app.api.ia.settings') as mock_settings:
        mock_settings.gemini_api_key = ''
        mock_settings.gemini_model = 'gemini-3.5-flash'
        mock_settings.groq_api_key = ''
        mock_settings.groq_model = 'llama-3.3-70b-versatile'

        resp = client.post('/v1/ia/govbi/probes', headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['status_geral'] == 'amarelo'
    assert data['resumo']['ignorados'] == 2


def test_status_ia_inclui_govbi_health_telemetry_persistida_e_probe(auth_headers):
    resp = client.get('/v1/ia/status', headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()['data']
    assert 'govbi_health' in data
    assert 'telemetry' in data
    assert 'telemetry_persistida' in data
    assert 'ultimo_probe_govbi' in data
    assert data['govbi_health']['produto'] == 'GovBI IA / ReqSys'
