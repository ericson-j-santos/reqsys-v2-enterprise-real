import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import require_admin
from app.main import app
from app.services import repository_admin

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_admin_dependency():
    previous = app.dependency_overrides.get(require_admin)
    app.dependency_overrides[require_admin] = lambda: {
        'sub': 'admin-teste',
        'papel': 'admin',
    }
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(require_admin, None)
        else:
            app.dependency_overrides[require_admin] = previous


def _registry(tmp_path, repositories):
    path = tmp_path / 'registry.json'
    path.write_text(
        json.dumps({'schema_version': '1.0.0', 'repositories': repositories}),
        encoding='utf-8',
    )
    return path


def test_registry_rejeita_duplicidade(tmp_path):
    item = {
        'name': 'acme/repo',
        'provider': 'github',
        'default_branch': 'main',
    }
    with pytest.raises(repository_admin.RepositoryAdminError):
        repository_admin.load_registry(_registry(tmp_path, [item, item]))


def test_checks_skipped_nao_viram_verde():
    summary = repository_admin.summarize_checks(
        [
            {
                'id': 1,
                'name': 'gate',
                'status': 'completed',
                'conclusion': 'skipped',
            }
        ]
    )
    assert summary['success'] == []
    assert summary['inconclusive'] == ['gate']


@patch('app.services.repository_admin.github_client.get_branch_sha', return_value='a' * 40)
def test_snapshot_vincula_sha_exato(_sha):
    snapshot = repository_admin.build_snapshot(
        'ericson-j-santos/reqsys-v2-enterprise-real'
    )
    assert snapshot['default_branch'] == 'main'
    assert snapshot['sha'] == 'a' * 40
    assert snapshot['mode'] == 'read_only'


@patch(
    'app.services.repository_admin.github_client.list_check_runs',
    return_value=[
        {
            'id': 10,
            'name': 'CI',
            'status': 'completed',
            'conclusion': 'failure',
        }
    ],
)
@patch(
    'app.services.repository_admin.github_client.get_pull_request',
    return_value={
        'state': 'open',
        'draft': False,
        'mergeable': True,
        'head': {'sha': 'b' * 40},
        'base': {'ref': 'main'},
    },
)
def test_decision_engine_classifica_ci_deterministico(_pr, _checks):
    result = repository_admin.decide_pull_request(
        'ericson-j-santos/reqsys-v2-enterprise-real',
        10,
    )
    assert result['decision'] == 'fix_ci'
    assert result['head_sha'] == 'b' * 40
    assert result['automatic_action_allowed'] is False


@patch(
    'app.services.repository_admin.github_client.list_check_runs',
    return_value=[
        {
            'id': 11,
            'name': 'CI',
            'status': 'completed',
            'conclusion': 'success',
        }
    ],
)
@patch(
    'app.services.repository_admin.github_client.get_pull_request',
    return_value={
        'state': 'open',
        'draft': False,
        'mergeable': True,
        'head': {'sha': 'c' * 40},
        'base': {'ref': 'main'},
    },
)
def test_decision_engine_somente_sinaliza_full_gates(_pr, _checks):
    result = repository_admin.decide_pull_request(
        'ericson-j-santos/reqsys-v2-enterprise-real',
        11,
    )
    assert result['decision'] == 'ready_for_full_gates'
    assert result['automatic_action_allowed'] is False


@patch('app.services.repository_admin.github_client.get_branch_sha', return_value='d' * 40)
def test_api_snapshot_retorna_envelope(_sha):
    response = client.get(
        '/v1/admin/repositories/ericson-j-santos/'
        'reqsys-v2-enterprise-real/snapshot'
    )
    assert response.status_code == 200
    assert response.json()['data']['sha'] == 'd' * 40


def test_api_rejeita_repo_fora_do_registry():
    response = client.get('/v1/admin/repositories/acme/outro/snapshot')
    assert response.status_code == 404
