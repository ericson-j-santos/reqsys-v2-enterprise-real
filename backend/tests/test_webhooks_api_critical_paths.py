"""Testes de caminhos críticos — API webhooks (GitHub, GitLab, Figma, async)."""

import hashlib
import hmac
import json
from unittest.mock import patch

from app.core.config import settings


def _github_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


def test_webhook_github_assinatura_ausente_com_secret(client, monkeypatch):
    monkeypatch.setattr(settings, 'github_webhook_secret', 'segredo-github')

    response = client.post(
        '/v1/webhooks/github',
        json={'zen': 'ping'},
        headers={'X-GitHub-Event': 'ping', 'Content-Type': 'application/json'},
    )

    assert response.status_code == 401
    assert 'ausente' in response.json()['detail'].lower()


def test_webhook_github_rejeita_assinatura_invalida(client, monkeypatch):
    monkeypatch.setattr(settings, 'github_webhook_secret', 'segredo-github')
    body = json.dumps({'zen': 'ping'}).encode()

    response = client.post(
        '/v1/webhooks/github',
        content=body,
        headers={
            'X-GitHub-Event': 'ping',
            'X-Hub-Signature-256': 'sha256=invalido',
            'Content-Type': 'application/json',
        },
    )

    assert response.status_code == 401


def test_webhook_github_assinatura_valida_aceita_ping(client, monkeypatch):
    secret = 'segredo-github'
    monkeypatch.setattr(settings, 'github_webhook_secret', secret)
    body = json.dumps({'zen': 'ping'}).encode()

    response = client.post(
        '/v1/webhooks/github',
        content=body,
        headers={
            'X-GitHub-Event': 'ping',
            'X-Hub-Signature-256': _github_signature(body, secret),
            'Content-Type': 'application/json',
        },
    )

    assert response.status_code == 200
    assert response.json()['data']['evento'] == 'ping'


def test_webhook_github_payload_json_invalido(client, monkeypatch):
    monkeypatch.setattr(settings, 'github_webhook_secret', '')

    response = client.post(
        '/v1/webhooks/github',
        content=b'{invalido',
        headers={'X-GitHub-Event': 'push', 'Content-Type': 'application/json'},
    )

    assert response.status_code == 400


def test_webhook_github_pull_request_processa_vinculos(client, monkeypatch):
    monkeypatch.setattr(settings, 'github_webhook_secret', '')
    payload = {
        'action': 'opened',
        'pull_request': {
            'number': 42,
            'title': 'feat: REQ-123456789 em PR',
            'html_url': 'https://github.com/o/r/pull/42',
            'head': {'ref': 'feature/req'},
            'base': {'ref': 'main'},
        },
        'repository': {'full_name': 'owner/repo'},
    }

    response = client.post(
        '/v1/webhooks/github',
        json=payload,
        headers={'X-GitHub-Event': 'pull_request'},
    )

    assert response.status_code == 200
    assert response.json()['data']['evento'] == 'pull_request'


def test_webhook_gitlab_rejeita_token_invalido(client, monkeypatch):
    monkeypatch.setattr(settings, 'gitlab_webhook_token', 'token-gitlab')

    response = client.post(
        '/v1/webhooks/gitlab',
        json={'object_kind': 'push'},
        headers={'X-Gitlab-Event': 'Push Hook', 'X-Gitlab-Token': 'errado'},
    )

    assert response.status_code == 401


def test_webhook_github_pr_acao_nao_suportada(client, monkeypatch):
    monkeypatch.setattr(settings, 'github_webhook_secret', '')
    payload = {
        'action': 'labeled',
        'pull_request': {'number': 1, 'title': 'sem codigo'},
        'repository': {'full_name': 'owner/repo'},
    }

    response = client.post(
        '/v1/webhooks/github',
        json=payload,
        headers={'X-GitHub-Event': 'pull_request'},
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['processado'] is True
    assert data['vinculos_criados'] == 0


def test_webhook_gitlab_push_com_vinculos(client, monkeypatch):
    monkeypatch.setattr(settings, 'gitlab_webhook_token', 'token-gitlab')
    payload = {
        'object_kind': 'push',
        'ref': 'refs/heads/main',
        'project': {'path_with_namespace': 'grupo/projeto'},
        'commits': [
            {
                'id': 'a' * 40,
                'message': 'feat: REQ-123456789 em commit',
                'author': {'name': 'Dev'},
                'url': 'https://gitlab.com/grupo/projeto/-/commit/aaa',
            }
        ],
    }

    response = client.post(
        '/v1/webhooks/gitlab',
        json=payload,
        headers={'X-Gitlab-Event': 'Push Hook', 'X-Gitlab-Token': 'token-gitlab'},
    )

    assert response.status_code == 200
    assert response.json()['data']['vinculos_criados'] >= 1


def test_webhook_gitlab_merge_request_evento(client, monkeypatch):
    monkeypatch.setattr(settings, 'gitlab_webhook_token', 'token-gitlab')
    payload = {
        'object_kind': 'merge_request',
        'object_attributes': {
            'title': 'MR sem codigo',
            'url': 'https://gitlab.com/g/p/-/merge_requests/1',
            'source_branch': 'feature',
            'target_branch': 'main',
        },
        'project': {'path_with_namespace': 'grupo/projeto'},
    }

    response = client.post(
        '/v1/webhooks/gitlab',
        json=payload,
        headers={'X-Gitlab-Event': 'Merge Request Hook', 'X-Gitlab-Token': 'token-gitlab'},
    )

    assert response.status_code == 200
    assert response.json()['data']['vinculos_criados'] == 0


def test_webhook_figma_sync_bidirectional(client, monkeypatch):
    monkeypatch.setattr(settings, 'figma_webhook_secret', '')
    monkeypatch.setattr(settings, 'figma_github_default_repo', 'owner/repo')
    sync_result = type('SyncResult', (), {'as_dict': lambda self: {'synced': True, 'direction': 'bidirectional'}})()

    with patch('app.api.webhooks.figma_github_sync.sync_bidirectional', return_value=sync_result):
        response = client.post(
            '/v1/webhooks/figma',
            json={'event_type': 'FILE_UPDATE', 'file_key': 'abc123'},
        )

    assert response.status_code == 200
    assert response.json()['data']['processado'] is True
    assert response.json()['data']['figma_github']['direction'] == 'bidirectional'


def test_webhook_figma_sem_file_key_retorna_motivo(client, monkeypatch):
    monkeypatch.setattr(settings, 'figma_webhook_secret', '')
    monkeypatch.setattr(settings, 'figma_github_default_repo', 'owner/repo')

    response = client.post('/v1/webhooks/figma', json={'event_type': 'FILE_UPDATE'})

    assert response.status_code == 200
    assert response.json()['data']['processado'] is False


def test_webhook_figma_payload_invalido(client, monkeypatch):
    monkeypatch.setattr(settings, 'figma_webhook_secret', '')

    response = client.post(
        '/v1/webhooks/figma',
        content=b'not-json',
        headers={'Content-Type': 'application/json'},
    )

    assert response.status_code == 400


def test_webhook_async_job_inexistente_retorna_404(client):
    response = client.get('/v1/webhooks/async-httpx/jobs/job-inexistente-xyz')

    assert response.status_code == 404


def test_webhook_github_issues_delega_figma_sync(client, monkeypatch):
    monkeypatch.setattr(settings, 'github_webhook_secret', '')
    sync_result = type('SyncResult', (), {'as_dict': lambda self: {'synced': True}})()

    with patch('app.api.webhooks.figma_github_sync.handle_github_issue_event', return_value=sync_result):
        response = client.post(
            '/v1/webhooks/github',
            json={'action': 'opened', 'issue': {'number': 1}},
            headers={'X-GitHub-Event': 'issues'},
        )

    assert response.status_code == 200
    assert response.json()['data']['figma_github']['synced'] is True
