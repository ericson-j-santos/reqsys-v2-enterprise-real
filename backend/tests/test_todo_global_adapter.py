import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import todo_global_adapter as adapter_api
from app.main import app
from app.schemas.todo_global import TodoGlobalUpsertRequest, TodoGlobalUpsertResponse
from app.services.todo_global_notion import NotionTodoGlobalClient, NotionTodoGlobalError


def _event(**todo_overrides):
    todo = {
        'title': 'E2E TODO Global adapter',
        'type': 'Validação',
        'external_id': 'issue-1693',
        'status': 'EM ANDAMENTO',
        'priority': 'P1',
        'next_action': 'Executar E2E real',
        'completion_criteria': 'Readback independente no Notion',
        'e2e_status': 'PARCIAL',
        'origin': 'GitHub issue #1693',
        'source': 'ReqSys',
    }
    todo.update(todo_overrides)
    return {
        'schema_version': '1.0',
        'event_id': 'evt-1693-adapter-0001',
        'event_type': 'todo.updated',
        'occurred_at': '2026-09-15T19:00:00Z',
        'correlation_id': 'corr-1693-adapter-0001',
        'idempotency_key': 'a' * 64,
        'project': 'ReqSys',
        'producer': 'pytest',
        'todo': todo,
    }


def _page(page_id: str, properties: dict) -> dict:
    return {'object': 'page', 'id': page_id, 'properties': properties}


@pytest.mark.asyncio
async def test_notion_upsert_cria_e_replay_fica_unchanged_sem_duplicar():
    state = {'properties': None, 'creates': 0, 'patches': 0, 'queries': 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode()) if request.content else {}
        if request.url.path.endswith('/query'):
            state['queries'] += 1
            results = [] if state['properties'] is None else [_page('page-1', state['properties'])]
            return httpx.Response(200, json={'object': 'list', 'results': results})
        if request.method == 'POST' and request.url.path == '/v1/pages':
            state['creates'] += 1
            state['properties'] = body['properties']
            return httpx.Response(200, json=_page('page-1', state['properties']))
        if request.method == 'PATCH' and request.url.path == '/v1/pages/page-1':
            state['patches'] += 1
            state['properties'] = body['properties']
            return httpx.Response(200, json=_page('page-1', state['properties']))
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url='https://api.notion.com', transport=transport) as http:
        client = NotionTodoGlobalClient(http, 'secret-test', 'ds-test')
        event = TodoGlobalUpsertRequest.model_validate(_event())
        first = await client.upsert(event)
        replay = await client.upsert(event)

    assert first.effect == 'created'
    assert first.readback_verified is True
    assert replay.effect == 'unchanged'
    assert replay.todo_id == first.todo_id == 'page-1'
    assert state['creates'] == 1
    assert state['patches'] == 0
    assert state['queries'] == 4


@pytest.mark.asyncio
async def test_notion_upsert_atualiza_item_existente():
    event = TodoGlobalUpsertRequest.model_validate(_event())
    desired = NotionTodoGlobalClient._properties(event)
    stale = dict(desired)
    stale['Status'] = {'select': {'name': 'PENDENTE'}}
    state = {'properties': stale, 'patches': 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode()) if request.content else {}
        if request.url.path.endswith('/query'):
            return httpx.Response(200, json={'results': [_page('page-1', state['properties'])]})
        if request.method == 'PATCH' and request.url.path == '/v1/pages/page-1':
            state['patches'] += 1
            state['properties'] = body['properties']
            return httpx.Response(200, json=_page('page-1', state['properties']))
        return httpx.Response(404, json={})

    async with httpx.AsyncClient(
        base_url='https://api.notion.com', transport=httpx.MockTransport(handler)
    ) as http:
        result = await NotionTodoGlobalClient(http, 'secret-test', 'ds-test').upsert(event)

    assert result.effect == 'updated'
    assert result.readback_verified is True
    assert state['patches'] == 1


@pytest.mark.asyncio
async def test_notion_upsert_falha_quando_readback_diverge():
    state = {'properties': None}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode()) if request.content else {}
        if request.url.path.endswith('/query'):
            if state['properties'] is None:
                return httpx.Response(200, json={'results': []})
            wrong = dict(state['properties'])
            wrong['Status'] = {'select': {'name': 'PENDENTE'}}
            return httpx.Response(200, json={'results': [_page('page-1', wrong)]})
        if request.method == 'POST' and request.url.path == '/v1/pages':
            state['properties'] = body['properties']
            return httpx.Response(200, json=_page('page-1', state['properties']))
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url='https://api.notion.com', transport=transport) as http:
        client = NotionTodoGlobalClient(http, 'secret-test', 'ds-test')
        with pytest.raises(NotionTodoGlobalError, match='notion_readback_projection_mismatch'):
            await client.upsert(TodoGlobalUpsertRequest.model_validate(_event()))


@pytest.mark.asyncio
async def test_notion_upsert_rejeita_chave_duplicada_na_fonte_canonica():
    event = TodoGlobalUpsertRequest.model_validate(_event())

    async def handler(_request: httpx.Request) -> httpx.Response:
        props = NotionTodoGlobalClient._properties(event)
        return httpx.Response(200, json={'results': [_page('page-1', props), _page('page-2', props)]})

    async with httpx.AsyncClient(
        base_url='https://api.notion.com', transport=httpx.MockTransport(handler)
    ) as http:
        client = NotionTodoGlobalClient(http, 'secret-test', 'ds-test')
        with pytest.raises(NotionTodoGlobalError, match='duplicate_idempotency_key'):
            await client.upsert(event)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('mode', 'expected'),
    [
        ('http', 'notion_http_500'),
        ('transport', 'notion_transport_error'),
        ('json', 'notion_invalid_json'),
    ],
)
async def test_notion_request_normaliza_falhas_remotas(mode, expected):
    async def handler(request: httpx.Request) -> httpx.Response:
        if mode == 'transport':
            raise httpx.ConnectError('falha', request=request)
        if mode == 'http':
            return httpx.Response(500, json={'secret': 'nao-propagar'})
        return httpx.Response(200, content=b'not-json')

    async with httpx.AsyncClient(
        base_url='https://api.notion.com', transport=httpx.MockTransport(handler)
    ) as http:
        client = NotionTodoGlobalClient(http, 'secret-test', 'ds-test')
        with pytest.raises(NotionTodoGlobalError, match=expected):
            await client._request('POST', '/v1/test', {})


@pytest.mark.asyncio
async def test_notion_query_rejeita_results_invalido():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'results': {'unexpected': True}})

    async with httpx.AsyncClient(
        base_url='https://api.notion.com', transport=httpx.MockTransport(handler)
    ) as http:
        client = NotionTodoGlobalClient(http, 'secret-test', 'ds-test')
        with pytest.raises(NotionTodoGlobalError, match='notion_query_invalid_results'):
            await client._query_exact('a' * 64)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('scenario', 'expected'),
    [
        ('create_missing_id', 'notion_create_missing_id'),
        ('existing_missing_id', 'notion_page_missing_id'),
        ('readback_identity', 'notion_readback_identity_mismatch'),
    ],
)
async def test_notion_upsert_rejeita_identidade_canonica_invalida(scenario, expected):
    event = TodoGlobalUpsertRequest.model_validate(_event())
    props = NotionTodoGlobalClient._properties(event)
    query_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal query_count
        if request.url.path.endswith('/query'):
            query_count += 1
            if scenario == 'existing_missing_id':
                return httpx.Response(200, json={'results': [{'properties': props}]})
            if query_count == 1:
                return httpx.Response(200, json={'results': []})
            return httpx.Response(200, json={'results': [_page('page-2', props)]})
        if request.method == 'POST' and request.url.path == '/v1/pages':
            if scenario == 'create_missing_id':
                return httpx.Response(200, json={})
            return httpx.Response(200, json=_page('page-1', props))
        return httpx.Response(404, json={})

    async with httpx.AsyncClient(
        base_url='https://api.notion.com', transport=httpx.MockTransport(handler)
    ) as http:
        client = NotionTodoGlobalClient(http, 'secret-test', 'ds-test')
        with pytest.raises(NotionTodoGlobalError, match=expected):
            await client.upsert(event)


def test_notion_projection_trata_campos_vazios_e_fonte_desconhecida():
    event = TodoGlobalUpsertRequest.model_validate(
        _event(source='Sistema externo', priority=None, e2e_status=None)
    )
    projection = NotionTodoGlobalClient._projection_from_event(event)
    properties = NotionTodoGlobalClient._properties(event)
    page_projection = NotionTodoGlobalClient._projection_from_page(
        {'properties': {'Título': {'title': []}, 'Tipo': {'select': None}}}
    )

    assert projection['Fonte'] == 'Outra'
    assert properties['Prioridade']['select'] is None
    assert properties['Status E2E']['select'] is None
    assert page_projection['Título'] is None
    assert page_projection['Tipo'] is None
    assert NotionTodoGlobalClient._source(None) is None


def test_config_notion_falha_fechado_sem_segredos(monkeypatch):
    monkeypatch.setattr(adapter_api, 'get_secret', lambda *_args, **_kwargs: '')
    with pytest.raises(HTTPException) as exc_info:
        adapter_api._notion_config()
    assert exc_info.value.status_code == 503


def test_config_notion_retorna_valores_do_cofre(monkeypatch):
    values = {
        'NOTION_TODO_GLOBAL_TOKEN': 'token-vault',
        'NOTION_TODO_GLOBAL_DATA_SOURCE_ID': 'data-source-vault',
    }
    monkeypatch.setattr(
        adapter_api,
        'get_secret',
        lambda name, **_kwargs: values.get(name, ''),
    )
    assert adapter_api._notion_config() == ('token-vault', 'data-source-vault')


@pytest.mark.asyncio
async def test_adapter_upsert_retorna_readback_verificado(monkeypatch):
    event = TodoGlobalUpsertRequest.model_validate(_event())

    class FakeNotionClient:
        def __init__(self, _client, token, data_source_id):
            assert token == 'token-test'
            assert data_source_id == 'ds-test'

        async def upsert(self, payload):
            return TodoGlobalUpsertResponse(
                todo_id='page-1',
                idempotency_key=payload.idempotency_key,
                effect='unchanged',
                canonical_status=payload.todo.status,
                readback_verified=True,
            )

    monkeypatch.setattr(adapter_api, '_notion_config', lambda: ('token-test', 'ds-test'))
    monkeypatch.setattr(adapter_api, 'NotionTodoGlobalClient', FakeNotionClient)

    result = await adapter_api.upsert_todo_global(event, _ctx={'kind': 'service_token'})
    assert result.readback_verified is True
    assert result.todo_id == 'page-1'


@pytest.mark.asyncio
async def test_adapter_upsert_converte_falha_notion_em_502(monkeypatch):
    event = TodoGlobalUpsertRequest.model_validate(_event())

    class FailingNotionClient:
        def __init__(self, _client, _token, _data_source_id):
            pass

        async def upsert(self, _payload):
            raise NotionTodoGlobalError('notion_transport_error')

    monkeypatch.setattr(adapter_api, '_notion_config', lambda: ('token-test', 'ds-test'))
    monkeypatch.setattr(adapter_api, 'NotionTodoGlobalClient', FailingNotionClient)

    with pytest.raises(HTTPException) as exc_info:
        await adapter_api.upsert_todo_global(event, _ctx={'kind': 'service_token'})
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == 'notion_transport_error'


def test_router_interno_resolve_e_exige_autenticacao():
    response = TestClient(app).post('/api/internal/todo-global/upsert', json=_event())
    assert response.status_code == 401


def test_router_todo_global_e_registrado_uma_unica_vez():
    upsert = [
        route
        for route in app.routes
        if getattr(route, 'path', None) == '/api/internal/todo-global/upsert'
        and 'POST' in (getattr(route, 'methods', None) or set())
    ]
    readiness = [
        route
        for route in app.routes
        if getattr(route, 'path', None) == '/api/internal/todo-global/readiness'
        and 'GET' in (getattr(route, 'methods', None) or set())
    ]

    assert len(upsert) == 1
    assert len(readiness) == 1


def test_concluido_sem_evidencia_e_criterio_e_rejeitado():
    with pytest.raises(ValidationError):
        TodoGlobalUpsertRequest.model_validate(
            _event(status='CONCLUÍDO', completion_criteria=None, evidence=None)
        )


@pytest.mark.asyncio
async def test_adapter_readiness_confirma_config_sem_expor_segredos(monkeypatch):
    monkeypatch.setattr(adapter_api, '_notion_config', lambda: ('token-test', 'ds-test'))

    result = await adapter_api.todo_global_readiness(_ctx={'kind': 'service_token'})

    assert result == {
        'ready': True,
        'adapter': 'notion',
        'notion_configured': True,
        'secret_value_exposed': False,
    }


def test_router_readiness_exige_autenticacao():
    response = TestClient(app).get('/api/internal/todo-global/readiness')
    assert response.status_code == 401
