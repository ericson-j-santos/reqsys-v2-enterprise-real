from app.services import figma_github_sync


def test_tokens_configurados_false_sem_segredos(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'figma_access_token', '')
    monkeypatch.setattr('app.services.github_client.get_secret', lambda key, default='': '')

    assert figma_github_sync.tokens_configurados() is False


def test_garantir_vinculos_demo_cria_links(client, monkeypatch):
    from app.core.config import settings
    from app.db import SessionLocal
    from app.models.integracao_figma_github import IntegracaoFigmaGithub

    monkeypatch.setattr(settings, 'figma_access_token', '')
    monkeypatch.setattr('app.services.github_client.get_secret', lambda key, default='': '')
    monkeypatch.setattr(settings, 'app_environment', 'development')

    with SessionLocal() as db:
        db.query(IntegracaoFigmaGithub).filter(
            IntegracaoFigmaGithub.figma_file_key == figma_github_sync.DEMO_FILE_KEY
        ).delete()
        db.commit()

    resp = client.get('/v1/integracoes/figma-github/status')
    assert resp.status_code == 200
    data = resp.json()['data']
    demo_items = [item for item in data['items'] if item['figma_file_key'] == figma_github_sync.DEMO_FILE_KEY]
    assert len(demo_items) >= 2
    assert data['modo_degradado'] is True
    assert demo_items[0]['github_issue_number']


def test_sync_modo_degradado_sem_tokens(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'figma_access_token', '')
    monkeypatch.setattr('app.services.github_client.get_secret', lambda key, default='': '')
    monkeypatch.setattr(settings, 'app_environment', 'development')

    resp = client.post('/v1/integracoes/figma-github/sync', json={'mode': 'bidirectional'})
    assert resp.status_code == 200
    body = resp.json()['data']
    assert body['modo_degradado'] is True
    assert body['created'] >= 0
    assert any('MODO_DEGRADADO' in warning for warning in body.get('warnings', []))
