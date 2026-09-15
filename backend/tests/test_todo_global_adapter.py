import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.todo_global import TodoGlobalUpsertRequest
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


def test_router_interno_resolve_e_exige_autenticacao():
    response = TestClient(app).post('/api/internal/todo-global/upsert', json=_event())
    assert response.status_code == 401


def test_concluido_sem_evidencia_e_criterio_e_rejeitado():
    with pytest.raises(ValidationError):
        TodoGlobalUpsertRequest.model_validate(
            _event(status='CONCLUÍDO', completion_criteria=None, evidence=None)
        )
