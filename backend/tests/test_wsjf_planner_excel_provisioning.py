import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.api.wsjf_planner_excel import wsjf_planner_excel_contract
from app.core.config import settings
from app.main import app
from app.services import wsjf_planner_excel_provisioning as provisioning
from app.services.wsjf_planner_excel_provisioning import (
    LOCAL_FIELDS,
    PROFILE,
    TABLE,
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
    response = FakeResponse()
    calls = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def patch(self, url, **kwargs):
        self.__class__.calls.append((url, kwargs))
        return self.__class__.response

    @classmethod
    def reset(cls, status_code=200, text='', json_body=None):
        cls.response = FakeResponse(status_code=status_code, text=text, json_body=json_body)
        cls.calls = []


def _payload(**overrides):
    data = {
        'environment_id': 'env-dev-001',
        'environment_url': 'https://org-dev.crm2.dynamics.com',
        'group_id': 'group-dev-001',
        'plan_id': 'plan-dev-001',
        'excel_source': 'groups/group-dev-001',
        'excel_drive': 'drive-dev-001',
        'excel_file': 'arquivo-dev-001',
        'planner_connection_id': 'planner-connection-dev',
        'excel_connection_id': 'excel-connection-dev',
        'target_environment': 'dev',
        'confirmar': False,
        'correlation_id': 'corr-wsjf-test',
    }
    data.update(overrides)
    return data


def _walk(actions):
    for action in actions.values():
        yield action
        nested = action.get('actions')
        if isinstance(nested, dict):
            yield from _walk(nested)
        else_actions = action.get('else', {}).get('actions')
        if isinstance(else_actions, dict):
            yield from _walk(else_actions)


def test_bundle_wsjf_tem_exatamente_um_fluxo_e_tb_demandas():
    bundle = montar_bundle(_payload())

    assert bundle['profile'] == PROFILE
    assert bundle['excel']['table'] == TABLE == 'tbDemandas'
    assert len(bundle['flows']) == 1
    assert bundle['flows'][0]['display_name'] == 'ReqSys WSJF - Planner para Excel'
    assert bundle['excel']['planner_is_source_of_truth'] is True
    assert set(bundle['excel']['local_fields_preserved']) == LOCAL_FIELDS


def test_fluxo_e_horario_e_nao_escreve_no_planner():
    definition = gerar_definicao(_payload())
    recurrence = definition['triggers']['Recorrencia']['recurrence']
    raw = json.dumps(definition, ensure_ascii=False)

    assert recurrence == {'frequency': 'Hour', 'interval': 1}
    assert 'ListTasks_V3' in raw
    assert 'UpdateTask_V2' not in raw
    assert 'UpdateTask_V3' not in raw
    assert validar_definicao(definition) == []


def test_atualizacao_preserva_campos_locais_excel():
    definition = gerar_definicao(_payload())
    patch_items = []
    for action in _walk(definition['actions']):
        host = action.get('inputs', {}).get('host', {})
        if host.get('operationId') == 'PatchItem':
            patch_items.append(action['inputs']['parameters']['item'])

    assert len(patch_items) == 1
    assert LOCAL_FIELDS.isdisjoint(patch_items[0].keys())
    assert patch_items[0]['TaskId'] == "@items('Para_cada_tarefa')?['id']"
    assert 'Sincronizado em' in patch_items[0]


def test_perfil_falha_fechado_fora_de_dev():
    with pytest.raises(ValueError, match='restrito a DEV'):
        montar_bundle(_payload(target_environment='prod'))


def test_contract_expoe_invariantes_do_mvp():
    result = wsjf_planner_excel_contract(_auth=object())
    data = result['data']

    assert data['profile'] == PROFILE
    assert data['excel_table'] == TABLE
    assert data['writes_back_to_planner'] is False
    assert set(data['local_fields_preserved']) == LOCAL_FIELDS


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


def test_despachar_confirmado_cria_fluxo_via_token_delegado(monkeypatch):
    FakeAsyncClient.reset(status_code=200, json_body={'name': 'flow-real-id'})
    monkeypatch.setattr(provisioning.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(despachar(_payload(confirmar=True), user_token='delegado-teste'))

    assert result['dispatched'] is True
    assert result['status'] == 'implantado'
    assert result['flow_id'] == 'flow-real-id'
    assert len(FakeAsyncClient.calls) == 1
    url, kwargs = FakeAsyncClient.calls[0]
    assert '/environments/env-dev-001/flows/' in url
    assert kwargs['headers']['Authorization'] == 'Bearer delegado-teste'
    body = kwargs['json']['properties']
    assert body['state'] == 'Stopped'
    assert body['connectionReferences']['shared_planner']['connectionName'] == 'planner-connection-dev'
    assert body['connectionReferences']['shared_excelonlinebusiness']['connectionName'] == 'excel-connection-dev'


def test_despachar_propaga_erro_http_sanitizado(monkeypatch):
    FakeAsyncClient.reset(status_code=403, text='consent_required')
    monkeypatch.setattr(provisioning.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(despachar(_payload(confirmar=True), user_token='delegado-teste'))

    assert result['dispatched'] is False
    assert result['status'] == 'erro_provisionamento'
    assert result['status_code'] == 403
    assert result['erro'] == 'consent_required'


def test_cors_preflight_permite_header_power_automate_token():
    client = TestClient(app)
    origin = settings.cors_origins_list[0]
    response = client.options(
        '/v1/hub-lowcode/wsjf/planner-excel/deploy',
        headers={
            'Origin': origin,
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'x-power-automate-token',
        },
    )
    assert response.status_code == 200
    allowed = response.headers.get('access-control-allow-headers', '').lower()
    assert 'x-power-automate-token' in allowed
