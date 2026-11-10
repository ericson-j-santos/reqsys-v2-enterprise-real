"""Contrato de acesso à fila global privada: JWT admin ou token com escopo EXATO.

A fila é global, não possui identificador de tenant: o endpoint não deve servir
como API de self-service multiusuário nem herdar escopo coringa de serviços.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api import todo_global_adapter as api
from app.core import service_tokens


class FakeDb:
    def __init__(self):
        self.commits = 0
        self.added = 0

    def add(self, obj):
        self.added += 1

    def commit(self):
        self.commits += 1


def read_ctx(*, service_token=None, jwt=None, db=None):
    credentials = (
        HTTPAuthorizationCredentials(scheme='Bearer', credentials=jwt)
        if jwt else None
    )
    return api.require_read_auth(
        x_service_token=service_token,
        credentials=credentials,
        db=db if db is not None else FakeDb(),
    )


def fake_service(scopes):
    return SimpleNamespace(scopes=scopes, label='teste', last_used_at=None)


def test_read_requires_authentication():
    with pytest.raises(HTTPException) as error:
        read_ctx()
    assert error.value.status_code == 401


def test_user_jwt_without_admin_role_is_denied(monkeypatch):
    monkeypatch.setattr(
        service_tokens, 'get_current_user',
        lambda credentials: {'papel': 'analista', 'sub': 'usuario-teste'},
    )
    with pytest.raises(HTTPException) as error:
        read_ctx(jwt='fake-token')
    assert error.value.status_code == 403


def test_admin_jwt_is_allowed(monkeypatch):
    monkeypatch.setattr(
        service_tokens, 'get_current_user',
        lambda credentials: {'papel': 'admin', 'sub': 'admin-teste'},
    )
    ctx = read_ctx(jwt='fake-token')
    assert ctx.via_token is False
    assert ctx.ator == 'admin-teste'


@pytest.mark.parametrize('scope', [
    '["todo_global:upsert"]',
    '["*"]',
    '[]',
])
def test_service_token_without_explicit_read_scope_is_denied(monkeypatch, scope):
    monkeypatch.setattr(
        service_tokens, '_resolver_token',
        lambda db, token: fake_service(scope),
    )
    db = FakeDb()
    with pytest.raises(HTTPException) as error:
        read_ctx(service_token='fake-token', db=db)
    assert error.value.status_code == 403
    assert db.commits == 0
    assert db.added == 0


def test_explicitly_scoped_service_token_is_allowed(monkeypatch):
    monkeypatch.setattr(
        service_tokens, '_resolver_token',
        lambda db, token: fake_service('["todo_global:read"]'),
    )
    db = FakeDb()
    ctx = read_ctx(service_token='fake-token', db=db)
    assert ctx.via_token is True
    assert ctx.ator == 'service-token:teste'
    assert db.commits == 1  # somente atualização auditável de last_used_at


def test_other_callers_keep_existing_wildcard_semantics():
    # Compatibilidade: só a leitura privada endurece o coringa.
    registro = fake_service('["*"]')
    assert service_tokens._tem_escopo(registro, 'todo_global:upsert') is True
    assert service_tokens._tem_escopo(
        registro, 'todo_global:read', aceitar_curinga=False
    ) is False

@pytest.mark.asyncio
async def test_queue_502_does_not_echo_upstream_detail(monkeypatch):
    from app.services.todo_global_notion import NotionTodoGlobalError

    class FailingNotion:
        def __init__(self, *args):
            pass

        async def read_queue(self, page_size, cursor):
            raise NotionTodoGlobalError('sensitive-exception-detail-secret')

    monkeypatch.setattr(api, '_notion_config', lambda: ('synthetic-secret', 'ds-test'))
    monkeypatch.setattr(api, 'NotionTodoGlobalClient', FailingNotion)
    with pytest.raises(HTTPException) as error:
        await api.read_todo_global_queue(page_size=10, cursor=None, _ctx=object())
    assert error.value.status_code == 502
    assert error.value.detail == 'Falha na integração com TODO Global'


@pytest.mark.asyncio
async def test_queue_bad_cursor_returns_generic_422(monkeypatch):
    from app.services.todo_global_notion import NotionTodoGlobalError

    class FailingNotion:
        def __init__(self, *args):
            pass

        async def read_queue(self, page_size, cursor):
            raise NotionTodoGlobalError('todo_read_invalid_cursor')

    monkeypatch.setattr(api, '_notion_config', lambda: ('synthetic-secret', 'ds-test'))
    monkeypatch.setattr(api, 'NotionTodoGlobalClient', FailingNotion)
    with pytest.raises(HTTPException) as error:
        await api.read_todo_global_queue(page_size=10, cursor='bad', _ctx=object())
    assert error.value.status_code == 422
    assert error.value.detail == 'Parâmetros de consulta inválidos'


@pytest.mark.asyncio
async def test_upsert_failure_never_echoes_upstream_detail(monkeypatch):
    from app.services.todo_global_notion import NotionTodoGlobalError

    class FailingNotion:
        def __init__(self, *args):
            pass

        async def upsert(self, payload):
            raise NotionTodoGlobalError('sensitive-exception-detail-secret')

    monkeypatch.setattr(api, '_notion_config', lambda: ('synthetic-secret', 'ds-test'))
    monkeypatch.setattr(api, 'NotionTodoGlobalClient', FailingNotion)
    with pytest.raises(HTTPException) as error:
        await api.upsert_todo_global(payload=object(), _ctx=object())
    assert error.value.status_code == 502
    assert error.value.detail == 'Falha na integração com TODO Global'
