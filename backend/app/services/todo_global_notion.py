from __future__ import annotations

from typing import Any

import httpx

from app.schemas.todo_global import TodoGlobalUpsertRequest, TodoGlobalUpsertResponse

NOTION_VERSION = '2026-03-11'
_TEXT_FIELDS = {
    'Chave de idempotência': 'idempotency_key',
    'Correlation ID': 'correlation_id',
    'Projeto': 'project',
    'Identificador externo': 'external_id',
    'Origem': 'origin',
    'Bloqueio': 'blocker',
    'Próxima ação': 'next_action',
    'Critério de conclusão': 'completion_criteria',
    'Evidência': 'evidence',
}
_URL_FIELDS = {'Origem URL': 'origin_url', 'Evidência URL': 'evidence_url'}
_SOURCE_OPTIONS = {'ChatGPT', 'ReqSys', 'GitHub', 'Notion', 'Outra'}


class NotionTodoGlobalError(RuntimeError):
    pass


def _rich_text(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    return [{'type': 'text', 'text': {'content': value}}]


def _plain_text(prop: dict[str, Any], kind: str) -> str | None:
    values = prop.get(kind) or []
    if not values:
        return None
    item = values[0]
    return item.get('plain_text') or (item.get('text') or {}).get('content') or None


def _select_value(prop: dict[str, Any]) -> str | None:
    select = prop.get('select')
    return select.get('name') if isinstance(select, dict) else None


class NotionTodoGlobalClient:
    def __init__(self, client: httpx.AsyncClient, token: str, data_source_id: str) -> None:
        self._client = client
        self._token = token
        self._data_source_id = data_source_id

    @property
    def _headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self._token}',
            'Notion-Version': NOTION_VERSION,
            'Content-Type': 'application/json',
        }

    async def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, headers=self._headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise NotionTodoGlobalError(f'notion_http_{exc.response.status_code}') from None
        except httpx.HTTPError:
            raise NotionTodoGlobalError('notion_transport_error') from None
        try:
            return response.json()
        except ValueError:
            raise NotionTodoGlobalError('notion_invalid_json') from None

    async def _query_exact(self, key: str) -> list[dict[str, Any]]:
        payload = {
            'filter': {
                'property': 'Chave de idempotência',
                'rich_text': {'equals': key},
            },
            'page_size': 2,
        }
        data = await self._request('POST', f'/v1/data_sources/{self._data_source_id}/query', payload)
        results = data.get('results')
        if not isinstance(results, list):
            raise NotionTodoGlobalError('notion_query_invalid_results')
        if len(results) > 1:
            raise NotionTodoGlobalError('duplicate_idempotency_key')
        return results

    @staticmethod
    def _source(value: str | None) -> str | None:
        if not value:
            return None
        return value if value in _SOURCE_OPTIONS else 'Outra'

    @classmethod
    def _projection_from_event(cls, event: TodoGlobalUpsertRequest) -> dict[str, Any]:
        todo = event.todo
        return {
            'Título': todo.title,
            'Chave de idempotência': event.idempotency_key,
            'Correlation ID': event.correlation_id,
            'Projeto': event.project,
            'Tipo': todo.type,
            'Status': todo.status,
            'Prioridade': todo.priority,
            'Fonte': cls._source(todo.source),
            'Identificador externo': todo.external_id,
            'Origem': todo.origin,
            'Origem URL': todo.origin_url,
            'Bloqueio': todo.blocker,
            'Próxima ação': todo.next_action,
            'Critério de conclusão': todo.completion_criteria,
            'Evidência': todo.evidence,
            'Evidência URL': todo.evidence_url,
            'Status E2E': todo.e2e_status,
        }

    @staticmethod
    def _projection_from_page(page: dict[str, Any]) -> dict[str, Any]:
        props = page.get('properties') or {}
        projection: dict[str, Any] = {'Título': _plain_text(props.get('Título', {}), 'title')}
        for notion_name in _TEXT_FIELDS:
            projection[notion_name] = _plain_text(props.get(notion_name, {}), 'rich_text')
        for notion_name in ('Tipo', 'Status', 'Prioridade', 'Fonte', 'Status E2E'):
            projection[notion_name] = _select_value(props.get(notion_name, {}))
        for notion_name in _URL_FIELDS:
            projection[notion_name] = (props.get(notion_name, {}) or {}).get('url')
        return projection

    @classmethod
    def _properties(cls, event: TodoGlobalUpsertRequest) -> dict[str, Any]:
        desired = cls._projection_from_event(event)
        props: dict[str, Any] = {
            'Título': {'title': _rich_text(desired['Título'])},
        }
        for notion_name in _TEXT_FIELDS:
            props[notion_name] = {'rich_text': _rich_text(desired[notion_name])}
        for notion_name in ('Tipo', 'Status', 'Prioridade', 'Fonte', 'Status E2E'):
            value = desired[notion_name]
            props[notion_name] = {'select': {'name': value} if value else None}
        for notion_name in _URL_FIELDS:
            props[notion_name] = {'url': desired[notion_name]}
        return props

    async def upsert(self, event: TodoGlobalUpsertRequest) -> TodoGlobalUpsertResponse:
        desired = self._projection_from_event(event)
        matches = await self._query_exact(event.idempotency_key)
        page_id: str
        effect: str
        if not matches:
            created = await self._request(
                'POST',
                '/v1/pages',
                {
                    'parent': {'type': 'data_source_id', 'data_source_id': self._data_source_id},
                    'properties': self._properties(event),
                },
            )
            page_id = str(created.get('id') or '')
            if not page_id:
                raise NotionTodoGlobalError('notion_create_missing_id')
            effect = 'created'
        else:
            page_id = str(matches[0].get('id') or '')
            if not page_id:
                raise NotionTodoGlobalError('notion_page_missing_id')
            current = self._projection_from_page(matches[0])
            if current == desired:
                effect = 'unchanged'
            else:
                await self._request(
                    'PATCH',
                    f'/v1/pages/{page_id}',
                    {'properties': self._properties(event)},
                )
                effect = 'updated'

        readback = await self._query_exact(event.idempotency_key)
        if len(readback) != 1 or str(readback[0].get('id') or '') != page_id:
            raise NotionTodoGlobalError('notion_readback_identity_mismatch')
        if self._projection_from_page(readback[0]) != desired:
            raise NotionTodoGlobalError('notion_readback_projection_mismatch')
        return TodoGlobalUpsertResponse(
            todo_id=page_id,
            idempotency_key=event.idempotency_key,
            effect=effect,
            canonical_status=event.todo.status,
            readback_verified=True,
        )
