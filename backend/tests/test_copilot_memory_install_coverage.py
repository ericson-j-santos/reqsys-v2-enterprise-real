import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.copilot_memory import require_copilot_memory_auth
from app.api.copilot_memory_install_discovery import require_install_auth
from app.core.config import settings
from app.core.service_tokens import ServiceAuthContext
from app.main import app
from app.services import copilot_memory_install_assistant as assistant
from app.services import copilot_memory_install_discovery as discovery


class FakeResponse:
    def __init__(self, payload=None, status_code=200, text=''):
        self._payload = payload or {}
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'http {self.status_code}')


class FakeAsyncClient:
    responses = {}
    calls = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    @classmethod
    def reset(cls, responses=None):
        cls.responses = responses or {}
        cls.calls = []

    def _response(self, method, url):
        self.__class__.calls.append((method, url))
        value = self.__class__.responses.get((method, url))
        if isinstance(value, Exception):
            raise value
        if value is None:
            return FakeResponse()
        return value

    async def get(self, url, **kwargs):
        return self._response('GET', url)

    async def post(self, url, **kwargs):
        return self._response('POST', url)

    async def put(self, url, **kwargs):
        return self._response('PUT', url)


def _set_microsoft_credentials(monkeypatch, enabled=True):
    monkeypatch.setattr(settings, 'azure_tenant_id', 'tenant-1' if enabled else '')
    monkeypatch.setattr(settings, 'azure_client_id', 'client-1' if enabled else '')
    monkeypatch.setattr(settings, 'azure_client_secret', 'secret-1' if enabled else '')


def _payload(confirmar=True):
    return {
        'environment_id': 'env-dev-001',
        'environment_url': 'https://org-dev.crm2.dynamics.com',
        'group_id': 'group-12345',
        'plan_id': 'plan-12345',
        'excel_source': 'groups/group-12345',
        'excel_drive': 'drive-12345',
        'excel_file': 'file-12345',
        'planner_connection_id': '/providers/Microsoft.PowerApps/apis/shared_planner/connections/planner-1',
        'excel_connection_id': '/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness/connections/excel-1',
        'target_environment': 'dev',
        'confirmar': confirmar,
        'correlation_id': 'cid-install-coverage',
    }


def test_token_falha_sem_credenciais(monkeypatch):
    _set_microsoft_credentials(monkeypatch, False)
    with pytest.raises(RuntimeError, match='Credenciais Microsoft Entra'):
        asyncio.run(assistant._token('scope'))


def test_token_retorna_access_token(monkeypatch):
    _set_microsoft_credentials(monkeypatch, True)
    url = 'https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token'
    FakeAsyncClient.reset({('POST', url): FakeResponse({'access_token': 'token-ok'})})
    monkeypatch.setattr(assistant.httpx, 'AsyncClient', FakeAsyncClient)

    assert asyncio.run(assistant._token('scope-x')) == 'token-ok'


def test_listar_ambientes_sem_credenciais(monkeypatch):
    _set_microsoft_credentials(monkeypatch, False)
    result = asyncio.run(assistant.listar_ambientes_instalacao())
    assert result['configurado'] is False
    assert result['ambientes'] == []


def test_listar_ambientes_mapeia_resposta(monkeypatch):
    _set_microsoft_credentials(monkeypatch, True)
    monkeypatch.setattr(assistant, '_token', AsyncMock(return_value='token'))
    url = f'{assistant._POWER_PLATFORM_BASE}/environmentmanagement/environments?api-version=2024-10-01'
    FakeAsyncClient.reset({
        ('GET', url): FakeResponse({'value': [
            {'id': 'env-1', 'displayName': 'DEV', 'url': 'https://dev.example', 'state': 'Ready', 'type': 'Sandbox', 'geo': 'brazil'},
            {'id': 'env-2', 'url': 'https://test.example', 'azureRegion': 'south'},
        ]})
    })
    monkeypatch.setattr(assistant.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(assistant.listar_ambientes_instalacao())
    assert result['erro'] is None
    assert result['ambientes'][0]['nome'] == 'DEV'
    assert result['ambientes'][1]['nome'] == 'env-2'
    assert result['ambientes'][1]['regiao'] == 'south'


def test_listar_ambientes_converte_erro(monkeypatch):
    _set_microsoft_credentials(monkeypatch, True)
    monkeypatch.setattr(assistant, '_token', AsyncMock(side_effect=RuntimeError('indisponivel')))
    result = asyncio.run(assistant.listar_ambientes_instalacao())
    assert result['configurado'] is True
    assert result['erro'] == 'indisponivel'


def test_listar_planos_valida_grupo_e_mapeia(monkeypatch):
    _set_microsoft_credentials(monkeypatch, True)
    vazio = asyncio.run(assistant.listar_planos_instalacao('   '))
    assert vazio['erro'] == 'Group ID obrigatorio'

    monkeypatch.setattr(assistant, '_token', AsyncMock(return_value='token'))
    url = f'{assistant._GRAPH_BASE}/groups/group-1/planner/plans'
    FakeAsyncClient.reset({('GET', url): FakeResponse({'value': [{'id': 'p1', 'title': 'Plano A'}, {'id': 'p2'}]})})
    monkeypatch.setattr(assistant.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(assistant.listar_planos_instalacao(' group-1 '))
    assert result['planos'] == [{'id': 'p1', 'titulo': 'Plano A'}, {'id': 'p2', 'titulo': 'p2'}]


def test_listar_planos_retorna_erro_sem_explodir(monkeypatch):
    _set_microsoft_credentials(monkeypatch, True)
    monkeypatch.setattr(assistant, '_token', AsyncMock(side_effect=RuntimeError('graph bloqueado')))
    result = asyncio.run(assistant.listar_planos_instalacao('group-1'))
    assert result['erro'] == 'graph bloqueado'


def test_listar_arquivos_excel_filtra_xlsx(monkeypatch):
    _set_microsoft_credentials(monkeypatch, True)
    vazio = asyncio.run(assistant.listar_arquivos_excel_grupo(''))
    assert vazio['erro'] == 'Group ID obrigatorio'

    monkeypatch.setattr(assistant, '_token', AsyncMock(return_value='token'))
    drive_url = f'{assistant._GRAPH_BASE}/groups/group-1/drive'
    files_url = f'{assistant._GRAPH_BASE}/groups/group-1/drive/root/children'
    FakeAsyncClient.reset({
        ('GET', drive_url): FakeResponse({'id': 'drive-1'}),
        ('GET', files_url): FakeResponse({'value': [
            {'id': 'f1', 'name': 'Memoria.xlsx', 'webUrl': 'https://excel/1'},
            {'id': 'f2', 'name': 'notas.txt', 'parentReference': {'driveId': 'drive-x'}},
        ]}),
    })
    monkeypatch.setattr(assistant.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(assistant.listar_arquivos_excel_grupo(' group-1 '))
    assert len(result['arquivos']) == 1
    assert result['arquivos'][0]['drive_id'] == 'drive-1'
    assert result['arquivos'][0]['excel_source'] == 'groups/group-1'


def test_listar_arquivos_excel_retorna_erro(monkeypatch):
    _set_microsoft_credentials(monkeypatch, True)
    monkeypatch.setattr(assistant, '_token', AsyncMock(side_effect=RuntimeError('drive negado')))
    result = asyncio.run(assistant.listar_arquivos_excel_grupo('group-1'))
    assert result['erro'] == 'drive negado'


def test_criar_planilha_valida_nome_e_envia_arquivo(monkeypatch):
    with pytest.raises(ValueError, match='Group ID'):
        asyncio.run(assistant.criar_planilha_excel_grupo(''))
    with pytest.raises(ValueError, match='xlsx'):
        asyncio.run(assistant.criar_planilha_excel_grupo('group-1', 'arquivo.csv'))

    monkeypatch.setattr(assistant, '_token', AsyncMock(return_value='token'))
    monkeypatch.setattr(assistant, 'gerar_planilha_xlsx', lambda: b'xlsx-bytes')
    put_url = f'{assistant._GRAPH_BASE}/groups/group-1/drive/root:/CopilotMemory.xlsx:/content'
    drive_url = f'{assistant._GRAPH_BASE}/groups/group-1/drive'
    FakeAsyncClient.reset({
        ('PUT', put_url): FakeResponse({'id': 'file-1', 'name': 'CopilotMemory.xlsx', 'webUrl': 'https://excel/file'}),
        ('GET', drive_url): FakeResponse({'id': 'drive-1'}),
    })
    monkeypatch.setattr(assistant.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(assistant.criar_planilha_excel_grupo('group-1', ''))
    assert result['id'] == 'file-1'
    assert result['drive_id'] == 'drive-1'


def test_listar_conexoes_separa_planner_excel(monkeypatch):
    _set_microsoft_credentials(monkeypatch, True)
    vazio = asyncio.run(assistant.listar_conexoes_instalacao('', user_token='delegado'))
    assert vazio['erro'] == 'Ambiente obrigatorio'

    url = f'{assistant._POWER_PLATFORM_BASE}/connectivity/environments/env-1/connections'
    FakeAsyncClient.reset({('GET', url): FakeResponse({'value': [
        {'name': 'planner-1', 'id': '/planner/1', 'properties': {'apiId': '/providers/Microsoft.PowerApps/apis/shared_planner', 'displayName': 'Planner principal'}},
        {'name': 'excel-1', 'id': '/excel/1', 'properties': {'connectorId': '/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness'}},
        {'name': 'other-1', 'type': 'shared_teams', 'properties': {}},
    ]})})
    monkeypatch.setattr(assistant.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(assistant.listar_conexoes_instalacao('env-1', user_token='delegado'))
    assert [item['id'] for item in result['planner']] == ['planner-1']
    assert [item['id'] for item in result['excel']] == ['excel-1']
    assert result['planner'][0]['nome'] == 'Planner principal'


def test_listar_conexoes_sem_token_delegado_nao_chama_rede(monkeypatch):
    _set_microsoft_credentials(monkeypatch, True)

    def _falha_se_chamado(*args, **kwargs):
        raise AssertionError('nao deveria chamar a rede sem token delegado')
    monkeypatch.setattr(assistant.httpx, 'AsyncClient', _falha_se_chamado)

    result = asyncio.run(assistant.listar_conexoes_instalacao('env-1'))
    assert result['planner'] == []
    assert result['excel'] == []
    assert 'token delegado' in result['erro'].lower()


def test_listar_conexoes_retorna_erro(monkeypatch):
    _set_microsoft_credentials(monkeypatch, True)

    class FakeAsyncClientFalha:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise RuntimeError('power platform negado')

    monkeypatch.setattr(assistant.httpx, 'AsyncClient', FakeAsyncClientFalha)
    result = asyncio.run(assistant.listar_conexoes_instalacao('env-1', user_token='delegado'))
    assert result['erro'] == 'power platform negado'


def test_bundle_rejeita_definicao_invalida(monkeypatch):
    monkeypatch.setattr(assistant, 'validar_definicao', lambda definition: ['erro-x'])
    with pytest.raises(ValueError, match='Definicao invalida'):
        assistant.montar_bundle_implantacao(_payload())


def test_status_assistente_sem_e_com_microsoft(monkeypatch):
    _set_microsoft_credentials(monkeypatch, False)
    monkeypatch.setattr(settings, 'github_pat', '')
    monkeypatch.setattr(settings, 'github_alm_repo', '')
    result = asyncio.run(assistant.status_assistente_instalacao())
    assert result['microsoft_configurado'] is False
    assert result['alm_configurado'] is False

    _set_microsoft_credentials(monkeypatch, True)
    monkeypatch.setattr(settings, 'github_pat', 'pat')
    monkeypatch.setattr(settings, 'github_alm_repo', 'owner/alm')
    monkeypatch.setattr(assistant, 'listar_ambientes_instalacao', AsyncMock(return_value={'ambientes': [{'id': 'env-1'}], 'erro': None}))
    result = asyncio.run(assistant.status_assistente_instalacao())
    assert result['ambientes'] == [{'id': 'env-1'}]
    assert result['alm_repository'] == 'owner/alm'


def test_dispatch_rejeita_bundle_grande(monkeypatch):
    monkeypatch.setattr(settings, 'github_pat', 'pat')
    monkeypatch.setattr(assistant, '_compactar_bundle', lambda bundle: 'x' * 60001)
    with pytest.raises(ValueError, match='excede o limite'):
        asyncio.run(assistant.despachar_implantacao(_payload()))


def test_dispatch_trata_erro_http_e_sucesso(monkeypatch):
    monkeypatch.setattr(settings, 'github_pat', 'pat')
    monkeypatch.setattr(settings, 'github_alm_repo', 'owner/alm')
    dispatch_url = f'https://api.github.com/repos/owner/alm/actions/workflows/{assistant._ALM_WORKFLOW}/dispatches'
    FakeAsyncClient.reset({('POST', dispatch_url): FakeResponse(status_code=422, text='input invalido')})
    monkeypatch.setattr(assistant.httpx, 'AsyncClient', FakeAsyncClient)

    erro = asyncio.run(assistant.despachar_implantacao(_payload()))
    assert erro['status'] == 'erro_dispatch'
    assert erro['status_code'] == 422
    assert erro['erro'] == 'input invalido'

    FakeAsyncClient.reset({('POST', dispatch_url): FakeResponse(status_code=204)})
    sucesso = asyncio.run(assistant.despachar_implantacao(_payload()))
    assert sucesso['dispatched'] is True
    assert sucesso['status'] == 'implantacao_solicitada'
    assert len(sucesso['flows']) == 3


def test_descoberta_grupos_sem_credenciais(monkeypatch):
    monkeypatch.setattr(discovery, '_credenciais_microsoft_configuradas', lambda: False)
    result = asyncio.run(discovery.listar_grupos_instalacao())
    assert result['configurado'] is False


def test_descoberta_grupos_filtra_unified_e_ordena(monkeypatch):
    monkeypatch.setattr(discovery, '_credenciais_microsoft_configuradas', lambda: True)
    monkeypatch.setattr(discovery, '_token', AsyncMock(return_value='token'))
    url = f'{discovery._GRAPH_BASE}/groups'
    FakeAsyncClient.reset({('GET', url): FakeResponse({'value': [
        {'id': 'g2', 'displayName': 'Zulu', 'groupTypes': ['Unified'], 'mail': 'z@example.com'},
        {'id': 'g0', 'displayName': 'Ignorar', 'groupTypes': []},
        {'id': 'g1', 'groupTypes': ['Unified'], 'mail': 'alpha@example.com'},
    ]})})
    monkeypatch.setattr(discovery.httpx, 'AsyncClient', FakeAsyncClient)

    result = asyncio.run(discovery.listar_grupos_instalacao())
    assert [item['id'] for item in result['grupos']] == ['g1', 'g2']
    assert result['grupos'][0]['nome'] == 'alpha@example.com'


def test_descoberta_grupos_retorna_erro(monkeypatch):
    monkeypatch.setattr(discovery, '_credenciais_microsoft_configuradas', lambda: True)
    monkeypatch.setattr(discovery, '_token', AsyncMock(side_effect=RuntimeError('graph indisponivel')))
    result = asyncio.run(discovery.listar_grupos_instalacao())
    assert result['erro'] == 'graph indisponivel'


client = TestClient(app)


def _auth_ctx():
    return ServiceAuthContext(ator='admin@teste', via_token=False)


@pytest.fixture
def install_auth_override():
    app.dependency_overrides[require_copilot_memory_auth] = _auth_ctx
    app.dependency_overrides[require_install_auth] = _auth_ctx
    yield
    app.dependency_overrides.pop(require_copilot_memory_auth, None)
    app.dependency_overrides.pop(require_install_auth, None)


def test_rotas_instalacao_happy_path(install_auth_override):
    with patch('app.api.copilot_memory.status_assistente_instalacao', new=AsyncMock(return_value={'microsoft_configurado': True})), \
         patch('app.api.copilot_memory.listar_planos_instalacao', new=AsyncMock(return_value={'planos': [{'id': 'p1'}]})), \
         patch('app.api.copilot_memory.listar_arquivos_excel_grupo', new=AsyncMock(return_value={'arquivos': [{'id': 'f1'}]})), \
         patch('app.api.copilot_memory.criar_planilha_excel_grupo', new=AsyncMock(return_value={'id': 'f1'})), \
         patch('app.api.copilot_memory.listar_conexoes_instalacao', new=AsyncMock(return_value={'planner': [], 'excel': []})), \
         patch('app.api.copilot_memory.validar_destino_assistente', new=AsyncMock(return_value={'id': 'env-dev'})), \
         patch('app.api.copilot_memory.despachar_implantacao', new=AsyncMock(return_value={'dispatched': True, 'correlation_id': 'cid-1'})):
        assert client.get('/v1/hub-lowcode/copilot-memory/install/status').status_code == 200
        assert client.get('/v1/hub-lowcode/copilot-memory/install/plans', params={'group_id': 'group-1'}).status_code == 200
        assert client.get('/v1/hub-lowcode/copilot-memory/install/files', params={'group_id': 'group-1'}).status_code == 200
        assert client.post('/v1/hub-lowcode/copilot-memory/install/workbook', params={'group_id': 'group-1'}).status_code == 200
        assert client.get('/v1/hub-lowcode/copilot-memory/install/connections', params={'environment_id': 'env-dev'}).status_code == 200
        response = client.post('/v1/hub-lowcode/copilot-memory/install/deploy', json=_payload())
        assert response.status_code == 200
        assert response.json()['data']['dispatched'] is True


def test_rotas_instalacao_erros_controlados(install_auth_override):
    with patch('app.api.copilot_memory.criar_planilha_excel_grupo', new=AsyncMock(side_effect=ValueError('arquivo invalido'))):
        response = client.post('/v1/hub-lowcode/copilot-memory/install/workbook', params={'group_id': 'group-1'})
        assert response.status_code == 409

    with patch('app.api.copilot_memory.validar_destino_assistente', new=AsyncMock(side_effect=ValueError('producao bloqueada'))):
        response = client.post('/v1/hub-lowcode/copilot-memory/install/deploy', json=_payload())
        assert response.status_code == 409


def test_rota_descoberta_grupos(install_auth_override):
    with patch('app.api.copilot_memory_install_discovery.listar_grupos_instalacao', new=AsyncMock(return_value={'grupos': [{'id': 'g1'}]})):
        response = client.get('/v1/hub-lowcode/copilot-memory/install/groups')
        assert response.status_code == 200
        assert response.json()['data']['grupos'][0]['id'] == 'g1'
