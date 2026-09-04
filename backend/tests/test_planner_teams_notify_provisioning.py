import asyncio
import json

import pytest

from app.services import planner_teams_notify_provisioning as provisioning
from app.services.planner_teams_notify_provisioning import (
    EVENTOS,
    PROFILE,
    despachar,
    gerar_definicao,
    montar_bundle,
    validar_definicao,
)


class FakeResponse:
    def __init__(self, status_code=200, text='', json_body=None):
        self.status_code = status_code
        self.text = text
        self._json_body = json_body if json_body is not None else {}

    def json(self):
        return self._json_body


class FakeAsyncClient:
    list_response = FakeResponse(json_body={'value': []})
    write_response = FakeResponse()
    calls = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **kwargs):
        self.__class__.calls.append(('GET', url, kwargs))
        return self.__class__.list_response

    async def patch(self, url, **kwargs):
        self.__class__.calls.append(('PATCH', url, kwargs))
        return self.__class__.write_response

    async def post(self, url, **kwargs):
        self.__class__.calls.append(('POST', url, kwargs))
        return self.__class__.write_response

    @classmethod
    def reset(cls, *, existing_flows=None, status_code=200, text='', json_body=None):
        cls.list_response = FakeResponse(json_body={'value': existing_flows or []})
        cls.write_response = FakeResponse(status_code=status_code, text=text, json_body=json_body)
        cls.calls = []


def _payload(**overrides):
    data = {
        'environment_id': 'env-dev-001',
        'environment_url': 'https://org-dev.crm2.dynamics.com',
        'group_id': 'group-dev-001',
        'plan_id': 'plan-dev-001',
        'planner_connection_id': 'planner-connection-dev',
        'teams_webhook_url': 'https://tieri.webhook.office.com/webhookb2/fake',
        'target_environment': 'dev',
        'confirmar': False,
        'correlation_id': 'corr-planner-teams-test',
    }
    data.update(overrides)
    return data


def test_bundle_tem_um_fluxo_por_evento():
    bundle = montar_bundle(_payload())

    assert bundle['profile'] == PROFILE
    assert {f['evento'] for f in bundle['flows']} == set(EVENTOS)
    assert all(f['state'] == 'Stopped' for f in bundle['flows'])


def test_definicao_usa_trigger_planner_permitido_e_nao_escreve_no_planner():
    for evento in EVENTOS:
        definicao = gerar_definicao(_payload(), evento)
        raw = json.dumps(definicao, ensure_ascii=False)

        assert validar_definicao(definicao) == []
        assert 'UpdateTask' not in raw
        assert definicao['actions']['Notificar_Teams']['type'] == 'Http'


def test_perfil_falha_fechado_fora_de_dev():
    with pytest.raises(ValueError, match='restrito a DEV'):
        montar_bundle(_payload(target_environment='prod'))


def test_perfil_falha_fechado_sem_webhook_configurado():
    with pytest.raises(ValueError, match='Webhook do Teams'):
        montar_bundle(_payload(teams_webhook_url=''))


def test_despachar_sem_confirmacao_apenas_valida():
    result = asyncio.run(despachar(_payload(confirmar=False)))

    assert result['dispatched'] is False
    assert result['status'] == 'validado_sem_implantar'
    assert result['bundle']['profile'] == PROFILE


def test_despachar_confirmado_falha_fechado_sem_token():
    result = asyncio.run(despachar(_payload(confirmar=True), user_token=None))

    assert result['dispatched'] is False
    assert result['status'] == 'pending_configuration'
    assert 'Flows.Manage.All' in result['erro']


def test_despachar_confirmado_cria_os_dois_fluxos_quando_nao_existem(monkeypatch):
    FakeAsyncClient.reset(existing_flows=[], status_code=200, json_body={'name': 'flow-real-id'})
    monkeypatch.setattr(provisioning.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(despachar(_payload(confirmar=True), user_token='delegado-teste'))

    assert result['dispatched'] is True
    assert result['status'] == 'implantado'
    assert {f['evento'] for f in result['flows']} == set(EVENTOS)
    assert all(f['dispatched'] and f['flow_id'] == 'flow-real-id' for f in result['flows'])
    metodos = [call[0] for call in FakeAsyncClient.calls]
    assert metodos == ['GET', 'POST', 'GET', 'POST']


def test_despachar_confirmado_atualiza_fluxo_existente_pelo_displayname(monkeypatch):
    FakeAsyncClient.reset(
        existing_flows=[{'name': 'id-ja-existente', 'properties': {'displayName': EVENTOS['criada']['display_name']}}],
        status_code=200,
        json_body={'name': 'id-ja-existente'},
    )
    monkeypatch.setattr(provisioning.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(despachar(_payload(confirmar=True), user_token='delegado-teste'))

    metodos_criada = [c for c in FakeAsyncClient.calls if c[1].endswith('id-ja-existente')]
    assert metodos_criada and metodos_criada[0][0] == 'PATCH'
    assert result['status'] in {'implantado', 'erro_parcial'}


def test_despachar_propaga_erro_http_sanitizado(monkeypatch):
    FakeAsyncClient.reset(existing_flows=[], status_code=403, text='consent_required')
    monkeypatch.setattr(provisioning.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(despachar(_payload(confirmar=True), user_token='delegado-teste'))

    assert result['dispatched'] is False
    assert result['status'] == 'erro_parcial'
    assert all(f['erro'] == 'consent_required' for f in result['flows'])
