"""Contratos do GET de fila privada: autorização, proveniência, negativos e replay."""
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import todo_global_adapter as api
from app.main import app
from app.schemas.todo_global import TodoGlobalQueueResponse
from app.services.todo_global_notion import NotionTodoGlobalClient, NotionTodoGlobalError


def _page(status='BLOQUEADO'):
    return {
        'object': 'page', 'id': 'page-001',
        'last_edited_time': '2026-11-08T10:30:00Z',
        'properties': {
            'Título': {'title': [{'plain_text': 'Host Noteri'}]},
            'Projeto': {'rich_text': [{'plain_text': 'Runtime Platform'}]},
            'Status': {'select': {'name': status}},
            'Prioridade': {'select': {'name': 'P0'}},
            'Bloqueio': {'rich_text': [{'plain_text': 'Gateway não validado'}]},
            'Próxima ação': {'rich_text': [{'plain_text': 'Preflight Risk1'}]},
        },
    }


def _transport(payload, calls):
    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == 'POST'  # POST de consulta Notion, não de alteração
        assert request.url.path == '/v1/data_sources/ds-test/query'
        assert request.headers['Authorization'] == 'Bearer secret-test'
        query = json.loads(request.content)
        assert set(query['filter']['or'][i]['select']['equals'] for i in range(3)) == {
            'PENDENTE', 'EM ANDAMENTO', 'BLOQUEADO'
        }
        assert query['sorts'][0]['timestamp'] == 'last_edited_time'
        return httpx.Response(200, json=payload)
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_queue_consulta_pendente_sem_mutar_e_projeta_apenas_campos_permitidos():
    calls = []
    data = {'results': [_page()], 'has_more': False, 'next_cursor': None}
    async with httpx.AsyncClient(base_url='https://api.notion.com',
                                 transport=_transport(data, calls)) as client:
        notion = NotionTodoGlobalClient(client, 'secret-test', 'ds-test')
        first = await notion.read_queue()
        replay = await notion.read_queue()
    result = TodoGlobalQueueResponse.model_validate(first)
    assert first == replay
    assert len(calls) == 2
    assert result.read_only is True and result.host_admitted is False
    assert result.items[0].title == 'Host Noteri'
    assert result.items[0].priority == 'P0'
    assert result.items[0].status == 'BLOQUEADO'
    assert set(first['items'][0]) == {
        'id', 'title', 'project', 'status', 'priority', 'blocker',
        'next_action', 'evidence_url', 'updated_at'
    }
    assert 'secret-test' not in str(first)


@pytest.mark.asyncio
async def test_queue_pagina_com_cursor_e_nunca_cria_todo():
    calls = []
    data = {'results': [_page()], 'has_more': True, 'next_cursor': 'page-next'}
    async with httpx.AsyncClient(base_url='https://api.notion.com',
                                 transport=_transport(data, calls)) as client:
        result = await NotionTodoGlobalClient(client, 'secret-test', 'ds-test').read_queue(
            page_size=1, cursor='cursor-123'
        )
    payload = json.loads(calls[0].content)
    assert payload['start_cursor'] == 'cursor-123'
    assert payload['page_size'] == 1
    assert result['next_cursor'] == 'page-next'
    assert result['has_more'] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(('case', 'expected'), [
    ({'results': [_page('CONCLUÍDO')], 'has_more': False, 'next_cursor': None}, 'unexpected_status'),
    ({'results': [], 'has_more': 'false', 'next_cursor': None}, 'invalid_pagination'),
    ({'results': [], 'has_more': True, 'next_cursor': None}, 'invalid_pagination'),
    ({'results': {'object': 'list'}, 'has_more': False, 'next_cursor': None}, 'invalid_results'),
    ({'results': [{}], 'has_more': False, 'next_cursor': None}, 'invalid_page'),
])
async def test_queue_rejeita_resposta_notion_adulterada(case, expected):
    async with httpx.AsyncClient(base_url='https://api.notion.com',
                                 transport=_transport(case, [])) as client:
        with pytest.raises(NotionTodoGlobalError, match=expected):
            await NotionTodoGlobalClient(client, 'secret-test', 'ds-test').read_queue()


@pytest.mark.asyncio
async def test_queue_rejeita_cursor_ou_limite_antes_de_qualquer_chamada():
    async with httpx.AsyncClient(base_url='https://api.notion.com',
                                 transport=_transport({}, [])) as client:
        notion = NotionTodoGlobalClient(client, 'secret-test', 'ds-test')
        with pytest.raises(NotionTodoGlobalError, match='invalid_cursor'):
            await notion.read_queue(cursor='http://invalid')
        with pytest.raises(NotionTodoGlobalError, match='invalid_page_size'):
            await notion.read_queue(page_size=101)


def test_queue_sem_credencial_e_negada_por_401():
    response = TestClient(app).get('/api/internal/todo-global/queue')
    assert response.status_code == 401
    assert 'token' not in response.text.lower() or 'credencial' in response.text.lower()


@pytest.mark.asyncio
async def test_queue_api_converte_falha_em_502_sem_expor_token(monkeypatch):
    class FailingNotion:
        def __init__(self, _client, _token, _ds):
            pass

        async def read_queue(self, page_size, cursor):
            raise NotionTodoGlobalError('notion_transport_error')

    monkeypatch.setattr(api, '_notion_config', lambda: ('secret-test', 'ds-test'))
    monkeypatch.setattr(api, 'NotionTodoGlobalClient', FailingNotion)
    with pytest.raises(HTTPException) as error:
        await api.read_todo_global_queue(_ctx={'kind': 'service'})
    assert error.value.status_code == 502
    assert 'secret-test' not in error.value.detail


def test_read_scope_distinto_do_upsert():
    assert api.require_read_auth is not api.require_upsert_auth
    assert api.read_todo_global_queue.__name__ == 'read_todo_global_queue'


@pytest.mark.asyncio
async def test_queue_rejeita_metadados_inconsistentes():
    base = _page()
    wrong_timestamp = {**base, 'last_edited_time': 'sem-timezone'}
    wrong_properties = {**base, 'properties': []}
    for row, expected in [
        (wrong_timestamp, 'invalid_updated_at'),
        (wrong_properties, 'invalid_properties'),
    ]:
        data = {'results': [row], 'has_more': False, 'next_cursor': None}
        async with httpx.AsyncClient(base_url='https://api.notion.com',
                                     transport=_transport(data, [])) as client:
            with pytest.raises(NotionTodoGlobalError, match=expected):
                await NotionTodoGlobalClient(client, 'secret-test', 'ds-test').read_queue()

    malformed_cursor = {'results': [], 'has_more': True, 'next_cursor': 'https://invalid'}
    async with httpx.AsyncClient(base_url='https://api.notion.com',
                                 transport=_transport(malformed_cursor, [])) as client:
        with pytest.raises(NotionTodoGlobalError, match='invalid_pagination'):
            await NotionTodoGlobalClient(client, 'secret-test', 'ds-test').read_queue()


@pytest.mark.asyncio
async def test_queue_api_publica_apenas_projecao_no_escopo_leitura(monkeypatch):
    class FakeNotion:
        def __init__(self, _client, token, data_source_id):
            assert token == 'secret-test'
            assert data_source_id == 'ds-test'

        async def read_queue(self, page_size, cursor):
            assert page_size == 10
            assert cursor is None
            return {
                'items': [{
                    'id': 'page-001', 'title': 'Host Noteri', 'project': 'Runtime',
                    'status': 'BLOQUEADO', 'priority': 'P0',
                    'blocker': 'Sem Gateway', 'next_action': 'Preflight',
                    'evidence_url': None, 'updated_at': '2026-11-08T10:30:00Z',
                }],
                'has_more': False, 'next_cursor': None,
                'source': 'notion', 'read_only': True, 'host_admitted': False,
            }

    monkeypatch.setattr(api, '_notion_config', lambda: ('secret-test', 'ds-test'))
    monkeypatch.setattr(api, 'NotionTodoGlobalClient', FakeNotion)
    result = await api.read_todo_global_queue(
        page_size=10, cursor=None, _ctx={'kind': 'admin'}
    )
    assert result.items[0].status == 'BLOQUEADO'
    assert result.host_admitted is False
    assert 'secret-test' not in result.model_dump_json()
