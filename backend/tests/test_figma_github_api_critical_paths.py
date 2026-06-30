"""Caminhos críticos — API Figma GitHub."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_sync_rejeita_sem_file_key_quando_default_ausente(monkeypatch):
    monkeypatch.setattr('app.api.figma_github.settings.figma_default_file_key', '')
    monkeypatch.setattr('app.api.figma_github.settings.figma_github_default_repo', 'org/repo')
    with patch('app.api.figma_github.figma_github_sync.sync_enabled', return_value=True):
        response = client.post(
            '/v1/integracoes/figma-github/sync',
            json={'repo': 'org/repo', 'mode': 'figma_to_github'},
        )
    assert response.status_code == 422


def test_sync_rejeita_sem_repo_quando_default_ausente(monkeypatch):
    monkeypatch.setattr('app.api.figma_github.settings.figma_default_file_key', 'file-key')
    monkeypatch.setattr('app.api.figma_github.settings.figma_github_default_repo', '')
    with patch('app.api.figma_github.figma_github_sync.sync_enabled', return_value=True):
        response = client.post(
            '/v1/integracoes/figma-github/sync',
            json={'file_key': 'file-key', 'mode': 'github_to_figma'},
        )
    assert response.status_code == 422


def test_sync_retorna_409_quando_feature_desabilitada(monkeypatch):
    with patch('app.api.figma_github.figma_github_sync.sync_enabled', return_value=False):
        response = client.post(
            '/v1/integracoes/figma-github/sync',
            json={'file_key': 'fk', 'repo': 'org/repo'},
        )
    assert response.status_code == 409


def test_status_filtra_por_repo_e_status():
    response = client.get(
        '/v1/integracoes/figma-github/status',
        params={'repo': 'org/inexistente', 'status': 'synced'},
    )
    assert response.status_code == 200
    assert response.json()['data']['total'] == 0
