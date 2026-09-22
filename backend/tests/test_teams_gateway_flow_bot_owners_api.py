"""Testes da API CRUD de donos/backups do canal flow_bot."""

import pytest
from fastapi.testclient import TestClient

from app.core.security import require_admin
from app.db import Base, SessionLocal, engine, get_db
from app.main import app
from app.models.teams_flow_bot_owner import TeamsFlowBotOwner

client = TestClient(app)


def _fake_admin():
    return {'papel': 'admin'}


@pytest.fixture
def admin_db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = _fake_admin
    try:
        yield session
    finally:
        session.query(TeamsFlowBotOwner).filter(TeamsFlowBotOwner.owner_email.like('teste-api-owner%')).delete(
            synchronize_session=False
        )
        session.commit()
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_admin, None)
        session.close()


def test_flow_bot_owners_sem_admin_retorna_401_ou_403():
    response = client.get('/v1/teams-gateway/flow-bot/owners')

    assert response.status_code in (401, 403)


def test_flow_bot_owners_crud_completo(admin_db):
    criar = client.post(
        '/v1/teams-gateway/flow-bot/owners',
        json={
            'owner_email': 'teste-api-owner-1@tieri659.onmicrosoft.com',
            'webhook_url': 'https://prod-00.brazilsouth.logic.azure.com:443/workflows/abc',
            'prioridade': 10,
        },
    )
    assert criar.status_code == 200
    body = criar.json()['data']
    owner_id = body['id']
    assert body['owner_email'] == 'teste-api-owner-1@tieri659.onmicrosoft.com'
    assert body['webhook_configurado'] is True
    assert 'webhook_url' not in body

    listar = client.get('/v1/teams-gateway/flow-bot/owners')
    assert listar.status_code == 200
    emails = [item['owner_email'] for item in listar.json()['data']['items']]
    assert 'teste-api-owner-1@tieri659.onmicrosoft.com' in emails

    atualizar = client.patch(f'/v1/teams-gateway/flow-bot/owners/{owner_id}', json={'ativo': False, 'prioridade': 5})
    assert atualizar.status_code == 200
    assert atualizar.json()['data']['ativo'] is False
    assert atualizar.json()['data']['prioridade'] == 5

    remover = client.delete(f'/v1/teams-gateway/flow-bot/owners/{owner_id}')
    assert remover.status_code == 200
    assert remover.json()['data']['removido'] is True

    atualizar_inexistente = client.patch('/v1/teams-gateway/flow-bot/owners/999999999', json={'ativo': True})
    assert atualizar_inexistente.status_code == 404


def test_flow_bot_owners_email_invalido_retorna_422(admin_db):
    response = client.post(
        '/v1/teams-gateway/flow-bot/owners',
        json={'owner_email': 'nao-e-email', 'webhook_url': 'https://exemplo.invalid/flow'},
    )

    assert response.status_code == 422
