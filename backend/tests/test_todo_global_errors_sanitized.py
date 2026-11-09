"""Regressão da sanitização de erros HTTP no adapter, sem rede."""
import ast
from pathlib import Path

import pytest
from fastapi import HTTPException

SOURCE = Path(__file__).resolve().parents[1] / 'app/api/todo_global_adapter.py'


def _raise_statement_for(*, operation: str, http_status: int):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == operation)
    candidates = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        if getattr(node.exc.func, 'id', None) != 'HTTPException':
            continue
        keywords = {k.arg:k.value for k in node.exc.keywords}
        if isinstance(keywords.get('status_code'), ast.Constant) and keywords['status_code'].value == http_status:
            candidates.append(node.exc)
    assert candidates, f'HTTP {http_status} ausente: {operation}'
    return candidates


@pytest.mark.parametrize('operation,status_code', [
    ('read_todo_global_queue', 422),
    ('read_todo_global_queue', 502),
    ('upsert_todo_global', 502),
])
def test_error_detail_is_constant_not_exception(operation, status_code):
    for call in _raise_statement_for(operation=operation, http_status=status_code):
        detail = next(k.value for k in call.keywords if k.arg == 'detail')
        assert isinstance(detail, ast.Constant) and isinstance(detail.value, str)
        assert len(detail.value) >= 10
        assert 'token' not in detail.value.lower()
        assert 'notion_transport_error' not in detail.value.lower()


def test_read_scope_cannot_be_used_to_upsert():
    text = SOURCE.read_text(encoding='utf-8')
    assert "require_upsert_auth = require_admin_or_service_token('todo_global:upsert')" in text
    assert "require_read_auth = require_admin_or_service_token('todo_global:read', aceitar_curinga=False)" in text
    assert "@router.get('/queue'" in text
    assert "@router.post('/upsert'" in text


def test_no_internal_error_or_secret_string_interpolation():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'detail=str(exc)' not in source
    assert 'return str(exc)' not in source
    assert 'detail=f' not in source
