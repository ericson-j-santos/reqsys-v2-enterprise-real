import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_phases_p1_p3.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from app.services.git_parser import extrair_codigos_agile, processar_pr_github_agile, processar_push_github_agile
from app.services.increment_gate_service import verificar_increment_gate


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_extrair_codigos_agile():
    assert extrair_codigos_agile('feat(AGI-123456789): story') == ['AGI-123456789']


def test_increment_gate_relaxado_em_teste():
    gate = verificar_increment_gate('new_front')
    assert gate['permitido'] is True


@patch('app.services.github_branch_service.github_client.create_branch')
@patch('app.services.github_branch_service.github_client.get_branch_sha')
@patch('app.services.github_branch_service.github_client.github_token_configurado', return_value=True)
def test_criar_branch_github_api(mock_token, mock_get_sha, mock_create_branch):
    client = TestClient(app)
    mock_get_sha.side_effect = lambda repo, branch: 'sha-base' if branch == 'dev' else None

    create_item = client.post(
        '/v1/agile-runtime/work-items',
        headers={'X-Correlation-Id': 'branch-api-test'},
        json={
            'tipo': 'story',
            'titulo': 'Criar branch via API GitHub',
            'descricao': 'Como desenvolvedor, quero criar branch automaticamente com increment gate.',
            'repositorio': 'org/reqsys',
        },
    )
    work_item_id = create_item.json()['data']['id']

    response = client.post(
        f'/v1/agile-runtime/work-items/{work_item_id}/github/branch',
        headers={'X-Correlation-Id': 'branch-api-test'},
        json={'ambiente': 'dev'},
    )
    assert response.status_code == 200
    payload = response.json()['data']
    assert payload['criada'] is True
    mock_create_branch.assert_called_once()


def test_webhook_github_push_com_agi_atualiza_work_item():
    client = TestClient(app)
    create_item = client.post(
        '/v1/agile-runtime/work-items',
        headers={'X-Correlation-Id': 'agi-webhook-test'},
        json={
            'tipo': 'story',
            'titulo': 'Webhook AGI sync',
            'descricao': 'Work item para validar sincronizacao AGI via webhook GitHub.',
            'repositorio': 'owner/repo',
        },
    )
    codigo_real = create_item.json()['data']['codigo']

    payload = {
        'ref': 'refs/heads/feature/backend/test-branch',
        'repository': {'full_name': 'owner/repo'},
        'commits': [
            {
                'id': 'c' * 40,
                'message': f'feat({codigo_real}): implementa webhook sync',
                'author': {'username': 'dev1'},
                'url': 'https://github.com/owner/repo/commit/ccc',
            }
        ],
    }
    eventos = processar_push_github_agile(payload)
    assert eventos and eventos[0]['work_item_codigo'] == codigo_real

    webhook_resp = client.post(
        '/v1/webhooks/github',
        json=payload,
        headers={'X-GitHub-Event': 'push'},
    )
    assert webhook_resp.status_code == 200
    data = webhook_resp.json()['data']
    assert data['work_items_atualizados'] == 1

    item_atualizado = next(
        item for item in client.get('/v1/agile-runtime/work-items').json()['data']
        if item['codigo'] == codigo_real
    )
    assert item_atualizado['branch'] == 'feature/backend/test-branch'
    assert item_atualizado['repositorio'] == 'owner/repo'


def test_webhook_github_pr_com_agi_atualiza_change_url():
    client = TestClient(app)
    create_item = client.post(
        '/v1/agile-runtime/work-items',
        json={
            'tipo': 'story',
            'titulo': 'PR webhook AGI',
            'descricao': 'Validar change_url automatico quando PR referencia AGI.',
            'repositorio': 'owner/repo',
        },
    )
    codigo_real = create_item.json()['data']['codigo']
    work_item_id = create_item.json()['data']['id']

    payload = {
        'action': 'opened',
        'pull_request': {
            'number': 99,
            'title': f'Implementa {codigo_real}',
            'body': f'Fecha {codigo_real}',
            'html_url': 'https://github.com/owner/repo/pull/99',
            'user': {'login': 'dev1'},
            'head': {'ref': 'feature/test-agi'},
            'merged': False,
        },
        'repository': {'full_name': 'owner/repo'},
    }
    eventos = processar_pr_github_agile(payload)
    assert eventos[0]['work_item_codigo'] == codigo_real

    webhook_resp = client.post(
        '/v1/webhooks/github',
        json=payload,
        headers={'X-GitHub-Event': 'pull_request'},
    )
    assert webhook_resp.status_code == 200
    assert webhook_resp.json()['data']['work_items_atualizados'] == 1

    item = next(
        row for row in client.get('/v1/agile-runtime/work-items').json()['data']
        if row['id'] == work_item_id
    )
    assert item['change_url'] == 'https://github.com/owner/repo/pull/99'
    assert item['change_id'] == '99'
