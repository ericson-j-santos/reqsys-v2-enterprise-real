import hashlib
import hmac
import json

import pytest

from app.db import SessionLocal
from app.models.integracao_figma_github import IntegracaoFigmaGithub


@pytest.fixture
def sync_case():
    file_key = 'figma-test-file'
    repo = 'acme/figma-sync'
    with SessionLocal() as db:
        db.query(IntegracaoFigmaGithub).filter(
            IntegracaoFigmaGithub.figma_file_key == file_key,
            IntegracaoFigmaGithub.github_repo == repo,
        ).delete()
        db.commit()
    return {'file_key': file_key, 'repo': repo}


def _fake_comment(message='Ajustar contraste do botao principal'):
    return {
        'id': 'comment-1',
        'message': message,
        'client_meta': {'node_id': '12:34'},
        'user': {'handle': 'designer'},
        'created_at': '2026-06-14T12:00:00Z',
    }


class TestClientesFigmaGithub:
    def test_figma_get_comments_normaliza_lista(self, monkeypatch):
        from app.services import figma_client

        monkeypatch.setattr(figma_client, '_request_json', lambda method, path, payload=None: {'comments': [_fake_comment()]})

        comments = figma_client.get_comments('abc123')

        assert len(comments) == 1
        assert comments[0]['id'] == 'comment-1'

    def test_github_create_issue_envia_payload(self, monkeypatch):
        from app.services import github_client

        calls = []

        def fake_request(method, path, payload=None):
            calls.append({'method': method, 'path': path, 'payload': payload})
            return {'number': 7, 'html_url': 'https://github.com/acme/repo/issues/7'}

        monkeypatch.setattr(github_client, '_request_json', fake_request)

        created = github_client.create_issue('acme/repo', 'Titulo', 'Corpo', labels=['figma'])

        assert created['number'] == 7
        assert calls[0]['method'] == 'POST'
        assert calls[0]['path'] == '/repos/acme/repo/issues'
        assert calls[0]['payload']['labels'] == ['figma']


class TestSyncManual:
    @pytest.fixture(autouse=True)
    def _habilitar_tokens_sync(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, 'figma_access_token', 'figma-test-token')
        monkeypatch.setattr(
            'app.services.github_client.get_secret',
            lambda key, default='': 'ghp-test-token' if key == 'GITHUB_TOKEN' else (default or ''),
        )

    def test_sync_manual_bidirecional_cria_vinculo_e_issue_fake(self, client, monkeypatch, sync_case):
        from app.services import figma_client, github_client

        monkeypatch.setattr(figma_client, 'get_comments', lambda file_key: [_fake_comment()])
        monkeypatch.setattr(figma_client, 'get_nodes', lambda file_key, node_ids: {'nodes': {}})
        monkeypatch.setattr(figma_client, 'create_comment', lambda file_key, message, node_id=None: {'id': 'figma-reply-1'})
        monkeypatch.setattr(github_client, 'find_issue_by_marker', lambda repo, marker: None)
        monkeypatch.setattr(
            github_client,
            'create_issue',
            lambda repo, title, body, labels=None: {
                'number': 101,
                'title': title,
                'body': body,
                'state': 'open',
                'html_url': 'https://github.com/acme/figma-sync/issues/101',
            },
        )

        resp = client.post('/v1/integracoes/figma-github/sync', json=sync_case)

        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['created'] == 1
        assert data['updated'] == 1
        assert data['links'][0]['github_issue_number'] == 101

    def test_segundo_sync_nao_duplica_issue(self, client, monkeypatch, sync_case):
        from app.services import figma_client, github_client

        monkeypatch.setattr(figma_client, 'get_comments', lambda file_key: [_fake_comment()])
        monkeypatch.setattr(figma_client, 'get_nodes', lambda file_key, node_ids: {'nodes': {}})
        monkeypatch.setattr(figma_client, 'create_comment', lambda file_key, message, node_id=None: {'id': 'figma-reply-1'})
        monkeypatch.setattr(github_client, 'find_issue_by_marker', lambda repo, marker: None)
        monkeypatch.setattr(
            github_client,
            'create_issue',
            lambda repo, title, body, labels=None: {
                'number': 102,
                'title': title,
                'body': body,
                'state': 'open',
                'html_url': 'https://github.com/acme/figma-sync/issues/102',
            },
        )

        first = client.post('/v1/integracoes/figma-github/sync', json={**sync_case, 'mode': 'figma_to_github'})
        second = client.post('/v1/integracoes/figma-github/sync', json={**sync_case, 'mode': 'figma_to_github'})

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()['data']['created'] == 1
        assert second.json()['data']['created'] == 0
        assert second.json()['data']['skipped'] == 1

    def test_github_vence_em_conflito(self, client, monkeypatch, sync_case):
        from app.services import figma_client, github_client

        monkeypatch.setattr(figma_client, 'get_nodes', lambda file_key, node_ids: {'nodes': {}})
        monkeypatch.setattr(github_client, 'find_issue_by_marker', lambda repo, marker: None)
        monkeypatch.setattr(
            github_client,
            'create_issue',
            lambda repo, title, body, labels=None: {
                'number': 103,
                'title': title,
                'body': body,
                'state': 'open',
                'html_url': 'https://github.com/acme/figma-sync/issues/103',
            },
        )

        monkeypatch.setattr(figma_client, 'get_comments', lambda file_key: [_fake_comment('Texto inicial')])
        resp1 = client.post('/v1/integracoes/figma-github/sync', json={**sync_case, 'mode': 'figma_to_github'})
        assert resp1.status_code == 200

        monkeypatch.setattr(figma_client, 'get_comments', lambda file_key: [_fake_comment('Texto alterado no Figma')])
        resp2 = client.post('/v1/integracoes/figma-github/sync', json={**sync_case, 'mode': 'figma_to_github'})

        assert resp2.status_code == 200
        data = resp2.json()['data']
        assert data['conflicts'] == 1
        status = client.get('/v1/integracoes/figma-github/status', params=sync_case).json()['data']['items'][0]
        assert status['status'] == 'conflict_resolved_github'


class TestWebhooksFigmaGithub:
    def test_webhook_figma_ping_retorna_200(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, 'figma_webhook_secret', '')

        resp = client.post('/v1/webhooks/figma', json={'event_type': 'PING'})

        assert resp.status_code == 200
        assert resp.json()['data']['processado'] is True

    def test_webhook_figma_assinatura_invalida_retorna_401(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, 'figma_webhook_secret', 'segredo')

        resp = client.post('/v1/webhooks/figma', json={'event_type': 'PING'}, headers={'X-Figma-Signature': 'errada'})

        assert resp.status_code == 401

    def test_webhook_figma_assinatura_valida_retorna_200(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, 'figma_webhook_secret', 'segredo')
        body = json.dumps({'event_type': 'PING'}).encode('utf-8')
        signature = hmac.new(b'segredo', body, hashlib.sha256).hexdigest()

        resp = client.post('/v1/webhooks/figma', content=body, headers={'X-Figma-Signature': signature, 'Content-Type': 'application/json'})

        assert resp.status_code == 200

    def test_webhook_github_issue_atualiza_figma(self, client, monkeypatch, sync_case):
        from app.services import figma_client

        with SessionLocal() as db:
            link = IntegracaoFigmaGithub(
                figma_file_key=sync_case['file_key'],
                figma_node_id='12:34',
                figma_comment_id='comment-1',
                github_repo=sync_case['repo'],
                github_issue_number=303,
                github_issue_url='https://github.com/acme/figma-sync/issues/303',
                sync_kind='comment',
            )
            db.add(link)
            db.commit()

        calls = []
        monkeypatch.setattr(figma_client, 'create_comment', lambda file_key, message, node_id=None: calls.append((file_key, message, node_id)) or {'id': 'reply'})

        resp = client.post(
            '/v1/webhooks/github',
            json={
                'action': 'edited',
                'repository': {'full_name': sync_case['repo']},
                'issue': {'number': 303, 'html_url': 'https://github.com/acme/figma-sync/issues/303', 'title': 'Issue'},
            },
            headers={'X-GitHub-Event': 'issues'},
        )

        assert resp.status_code == 200
        assert resp.json()['data']['figma_github']['updated'] == 1
        assert calls[0][0] == sync_case['file_key']
