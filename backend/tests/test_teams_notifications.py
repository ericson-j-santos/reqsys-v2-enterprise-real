"""Testes do painel central de notificações Microsoft Teams."""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user, require_admin
from app.db import Base, SessionLocal, engine, get_db
from app.main import app
from app.models.integracao_log import IntegracaoLog
from app.models.teams_notification_queue import TeamsNotificationQueueItem
from app.services import teams_notifications

client = TestClient(app)


def _fake_admin():
    return {'papel': 'admin', 'sub': 'test-admin'}


@pytest.fixture
def notification_db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _fake_admin
    app.dependency_overrides[require_admin] = _fake_admin
    try:
        yield session
    finally:
        session.query(TeamsNotificationQueueItem).filter(
            TeamsNotificationQueueItem.correlation_id.like('test-notification-%')
        ).delete(synchronize_session=False)
        session.query(IntegracaoLog).filter(
            IntegracaoLog.correlation_id.like('test-notification-%')
        ).delete(synchronize_session=False)
        session.commit()
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(require_admin, None)
        session.close()


def test_endpoints_exigem_autenticacao():
    response = client.get('/v1/teams-gateway/notificacoes/dashboard')
    assert response.status_code in (401, 403)


def test_enfileirar_mascara_destino_e_consolida_dashboard(notification_db, monkeypatch):
    async def fake_send(request, db, correlation_id):
        db.add(
            IntegracaoLog(
                tipo='teams_gateway',
                status='sucesso',
                titulo='Teams Gateway via flow_bot',
                autor=request.autor,
                mensagem=request.texto[:200],
                detalhes=json.dumps(
                    {
                        'canal_usado': 'flow_bot',
                        'metadata': request.metadata,
                        'provider_response': {'status_code': 202},
                    }
                ),
                correlation_id=correlation_id,
            )
        )
        db.commit()
        return {
            'entregue': True,
            'canal_usado': 'flow_bot',
            'status_code': 202,
            'message_id': 'message-test-1',
            'correlation_id': correlation_id,
        }

    monkeypatch.setattr(teams_notifications, 'enviar_mensagem_gateway', fake_send)

    response = client.post(
        '/v1/teams-gateway/notificacoes/enfileirar',
        json={
            'origem': 'ci',
            'tipo_evento': 'workflow_failure',
            'ambiente': 'dev',
            'correlation_id': 'test-notification-success',
            'titulo': 'Falha no CI',
            'texto': 'Resumo sanitizado da falha.',
            'destino_tipo': 'chat',
            'destino_id': 'usuario.teste@example.com',
            'modo': 'flow_bot',
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['status_evento'] == 'ENVIADO'
    assert data['upn_destino'].endswith('@example.com')
    assert data['upn_destino'] != 'usuario.teste@example.com'
    assert 'usuario.teste@example.com' not in response.text
    assert len(data['destino_hash']) == 64
    assert data['status_http'] == 202

    dashboard = client.get('/v1/teams-gateway/notificacoes/dashboard')
    assert dashboard.status_code == 200
    body = dashboard.json()['data']
    assert body['enviados'] >= 1
    assert body['por_origem']['ci'] >= 1
    assert body['cobertura']['dlq_reprocessamento'] is True

    fila = client.get('/v1/teams-gateway/notificacoes/fila')
    assert fila.status_code == 200
    assert any(item['correlation_id'] == 'test-notification-success' for item in fila.json()['data'])

    logs = client.get('/v1/teams-gateway/notificacoes/logs')
    assert logs.status_code == 200
    assert any('correlation_id=test-notification-success' in item['detalhe'] for item in logs.json()['data'])


def test_falha_entra_na_dlq_e_reprocessa(notification_db, monkeypatch):
    attempts = {'count': 0}

    async def fake_send(request, db, correlation_id):
        attempts['count'] += 1
        delivered = attempts['count'] > 1
        db.add(
            IntegracaoLog(
                tipo='teams_gateway',
                status='sucesso' if delivered else 'erro',
                titulo='Teams Gateway via webhook',
                autor=request.autor,
                mensagem=request.texto[:200],
                detalhes=json.dumps(
                    {
                        'canal_usado': 'webhook',
                        'erro': None if delivered else 'http_503',
                        'metadata': request.metadata,
                        'provider_response': {'status_code': 200 if delivered else 503},
                    }
                ),
                correlation_id=correlation_id,
            )
        )
        db.commit()
        return {
            'entregue': delivered,
            'canal_usado': 'webhook',
            'status_code': 200 if delivered else 503,
            'message_id': 'message-test-2' if delivered else None,
            'erro': None if delivered else 'http_503',
            'correlation_id': correlation_id,
        }

    monkeypatch.setattr(teams_notifications, 'enviar_mensagem_gateway', fake_send)

    created = client.post(
        '/v1/teams-gateway/notificacoes/enfileirar',
        json={
            'origem': 'hitl',
            'tipo_evento': 'approval_required',
            'ambiente': 'stg',
            'correlation_id': 'test-notification-retry',
            'titulo': 'Aprovação necessária',
            'texto': 'Existe uma aprovação governada pendente.',
            'destino_tipo': 'canal',
            'modo': 'webhook',
            'max_tentativas': 3,
        },
    )
    assert created.status_code == 200
    event = created.json()['data']
    assert event['status_evento'] == 'FALHA'
    assert event['status_http'] == 503

    dlq = client.get('/v1/teams-gateway/notificacoes/dlq')
    assert dlq.status_code == 200
    assert any(item['id_dlq'] == event['id_evento'] for item in dlq.json()['data'])

    replay = client.post(
        f"/v1/teams-gateway/notificacoes/dlq/reprocessar/{event['id_evento']}"
    )
    assert replay.status_code == 200
    assert replay.json()['data']['status_evento'] == 'ENVIADO'
    assert replay.json()['data']['tentativas'] == 2
