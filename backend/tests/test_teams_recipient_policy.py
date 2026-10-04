"""Testes do cadastro dinamico e fan-out por politica do Teams Gateway."""

import pytest
from fastapi.testclient import TestClient

from app.core.security import require_admin
from app.db import Base, SessionLocal, engine, get_db
from app.main import app
from app.models.teams_notification_recipient import TeamsNotificationRecipient
from app.schemas.teams_recipient_policy import TeamsRecipientPolicyMessageRequest
from app.services import teams_recipient_policy as service

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
    session.query(TeamsNotificationRecipient).filter(
        TeamsNotificationRecipient.politica == 'hitl-approvers-test'
    ).delete(synchronize_session=False)
    session.commit()
    try:
        yield session
    finally:
        session.query(TeamsNotificationRecipient).filter(
            TeamsNotificationRecipient.politica == 'hitl-approvers-test'
        ).delete(synchronize_session=False)
        session.commit()
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_admin, None)
        session.close()


def test_recipient_policy_crud_sem_secrets(admin_db):
    for index in (1, 2):
        response = client.post(
            '/v1/teams-gateway/recipient-policies/recipients',
            json={
                'politica': 'hitl-approvers-test',
                'nome': f'Aprovador {index}',
                'destino_id': f'aprovador{index}@example.com',
                'destino_tipo': 'chat',
                'prioridade': index,
            },
        )
        assert response.status_code == 200

    listar = client.get(
        '/v1/teams-gateway/recipient-policies/recipients',
        params={'politica': 'hitl-approvers-test', 'apenas_ativos': True},
    )
    assert listar.status_code == 200
    itens = listar.json()['data']['items']
    assert [item['nome'] for item in itens] == ['Aprovador 1', 'Aprovador 2']


@pytest.mark.asyncio
async def test_delivery_mode_all_envia_para_todos_sem_expor_destino(admin_db, monkeypatch):
    admin_db.add_all(
        [
            TeamsNotificationRecipient(
                politica='hitl-approvers-test',
                nome='Aprovador 1',
                destino_id='aprovador1@example.com',
                destino_tipo='chat',
                prioridade=1,
            ),
            TeamsNotificationRecipient(
                politica='hitl-approvers-test',
                nome='Aprovador 2',
                destino_id='aprovador2@example.com',
                destino_tipo='chat',
                prioridade=2,
            ),
        ]
    )
    admin_db.commit()
    capturados = []

    async def fake_send(request, *, db, correlation_id):
        capturados.append(request.destino_id)
        return {
            'entregue': True,
            'canal_usado': 'flow_bot',
            'correlation_id': correlation_id,
            'erro': None,
            'motivo': None,
        }

    monkeypatch.setattr(service, 'enviar_mensagem_gateway', fake_send)
    payload = TeamsRecipientPolicyMessageRequest(
        destino_tipo='auto',
        modo='auto',
        texto='Aprovacao necessaria',
        autor='reqsys-hitl',
        delivery_mode='all',
    )
    resultado = await service.enviar_mensagem_por_politica(
        'hitl-approvers-test',
        payload,
        db=admin_db,
        correlation_id='corr-test',
    )

    assert capturados == ['aprovador1@example.com', 'aprovador2@example.com']
    assert resultado['entregue'] is True
    assert resultado['provider_response']['delivered'] == 2
    assert 'aprovador1@example.com' not in str(resultado['provider_response'])


@pytest.mark.asyncio
async def test_sem_cadastro_usa_destino_explicito_apenas_como_fallback(admin_db, monkeypatch):
    async def fake_send(request, *, db, correlation_id):
        return {
            'entregue': True,
            'canal_usado': 'flow_bot',
            'correlation_id': correlation_id,
            'provider_response': {},
        }

    monkeypatch.setattr(service, 'enviar_mensagem_gateway', fake_send)
    payload = TeamsRecipientPolicyMessageRequest(
        destino_tipo='chat',
        destino_id='fallback@example.com',
        texto='Aprovacao necessaria',
        delivery_mode='all',
    )
    resultado = await service.enviar_mensagem_por_politica(
        'hitl-approvers-test',
        payload,
        db=admin_db,
        correlation_id='corr-fallback',
    )
    assert resultado['entregue'] is True
    assert resultado['fallback_usado'] is True
    assert resultado['provider_response']['resolution'] == 'explicit_destination_fallback'
