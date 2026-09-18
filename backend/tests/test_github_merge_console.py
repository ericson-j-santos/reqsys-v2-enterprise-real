from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import require_admin
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_admin_dependency():
    previous = app.dependency_overrides.get(require_admin)
    app.dependency_overrides[require_admin] = lambda: {'sub': 'admin-teste', 'papel': 'admin'}
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(require_admin, None)
        else:
            app.dependency_overrides[require_admin] = previous

PR = {
    'title': 'PR empilhada',
    'state': 'open',
    'draft': False,
    'mergeable': True,
    'html_url': 'https://github.com/acme/repo/pull/10',
    'head': {'sha': 'a' * 40, 'ref': 'feature'},
    'base': {'ref': 'main'},
}


@patch('app.api.github_merge_console.github_client.list_check_runs', return_value=[])
@patch('app.api.github_merge_console.github_client.get_pull_request', return_value=PR)
def test_consulta_pr_retorna_guardrails(_pr, _checks):
    response = client.get('/v1/admin/github-merge/pull-requests/10?repositorio=acme/repo')
    assert response.status_code == 200
    assert response.json()['data']['sha'] == 'a' * 40


@patch('app.api.github_merge_console.github_client.request_async_merge', return_value={'status': 'pending', 'uuid': 'u'})
@patch('app.api.github_merge_console.github_client.list_check_runs', return_value=[])
@patch('app.api.github_merge_console.github_client.get_pull_request', return_value=PR)
def test_solicita_merge_com_sha_imutavel(_pr, _checks, merge):
    response = client.post(
        '/v1/admin/github-merge/merge-assincrono',
        json={
            'repositorio': 'acme/repo',
            'pull_request': 10,
            'sha_esperado': 'a' * 40,
            'metodo': 'squash',
            'acao': 'default',
            'titulo_commit': 'feat: merge governado',
            'mensagem_commit': 'evidencia',
        },
    )
    assert response.status_code == 200
    merge.assert_called_once()


@patch('app.api.github_merge_console.github_client.list_check_runs', return_value=[])
@patch('app.api.github_merge_console.github_client.get_pull_request', return_value=PR)
def test_bloqueia_sha_divergente(_pr, _checks):
    response = client.post(
        '/v1/admin/github-merge/merge-assincrono',
        json={
            'repositorio': 'acme/repo',
            'pull_request': 10,
            'sha_esperado': 'b' * 40,
            'titulo_commit': 'feat: merge governado',
        },
    )
    assert response.status_code == 409
    assert 'SHA divergente' in response.json()['detail']

