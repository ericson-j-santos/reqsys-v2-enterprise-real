"""Testes de failover multi-dono do canal flow_bot (donos cadastrados no banco)."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.db import Base, SessionLocal, engine
from app.models.teams_flow_bot_owner import TeamsFlowBotOwner
from app.schemas.teams_gateway import TeamsGatewayMessageRequest
from app.services import teams_gateway as svc


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.query(TeamsFlowBotOwner).filter(TeamsFlowBotOwner.owner_email.like('teste-multi-owner%')).delete(
            synchronize_session=False
        )
        session.commit()
        session.close()


def _criar_owner(db, email, prioridade, ativo=True, webhook='https://exemplo.invalid/flow'):
    item = TeamsFlowBotOwner(owner_email=email, webhook_url=webhook, prioridade=prioridade, ativo=ativo)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_flow_bot_alvos_ordena_por_prioridade_e_ignora_inativos(db_session):
    _criar_owner(db_session, 'teste-multi-owner-b@tieri659.onmicrosoft.com', prioridade=50)
    _criar_owner(db_session, 'teste-multi-owner-a@tieri659.onmicrosoft.com', prioridade=10)
    _criar_owner(db_session, 'teste-multi-owner-c-inativo@tieri659.onmicrosoft.com', prioridade=5, ativo=False)

    alvos = svc._flow_bot_alvos(db_session)

    emails = [email for email, _ in alvos]
    assert emails == [
        'teste-multi-owner-a@tieri659.onmicrosoft.com',
        'teste-multi-owner-b@tieri659.onmicrosoft.com',
    ]


@patch('app.services.teams_gateway._enviar_flow_bot_webhook', new_callable=AsyncMock)
def test_enviar_flow_bot_faz_failover_quando_primeiro_dono_falha(mock_enviar, db_session):
    _criar_owner(db_session, 'teste-multi-owner-primario@tieri659.onmicrosoft.com', prioridade=1)
    _criar_owner(db_session, 'teste-multi-owner-backup@tieri659.onmicrosoft.com', prioridade=2)

    async def _side_effect(url, destinatario, texto, metadata, correlation_id, circuit):
        if 'primario' in circuit.name:
            raise RuntimeError('flow desligado (dono de ferias)')
        return {'status_code': 202}

    mock_enviar.side_effect = _side_effect
    payload = TeamsGatewayMessageRequest(
        destino_tipo='chat', destino_id='fulano@tieri659.onmicrosoft.com', texto='Ola', modo='flow_bot'
    )

    resultado = _run(svc.enviar_mensagem_gateway(payload, db=db_session, correlation_id='corr-multi-1'))

    assert resultado['entregue'] is True
    assert resultado['canal_usado'] == 'flow_bot'
    assert resultado['provider_response']['owner'] == 'teste-multi-owner-backup@tieri659.onmicrosoft.com'
    assert resultado['provider_response']['tentativas_anteriores'] == 1
    assert mock_enviar.await_count == 2


@patch('app.services.teams_gateway._enviar_flow_bot_webhook', new_callable=AsyncMock)
def test_enviar_flow_bot_falha_quando_todos_os_donos_falham(mock_enviar, db_session):
    _criar_owner(db_session, 'teste-multi-owner-um@tieri659.onmicrosoft.com', prioridade=1)
    _criar_owner(db_session, 'teste-multi-owner-dois@tieri659.onmicrosoft.com', prioridade=2)
    mock_enviar.side_effect = RuntimeError('todos os flows desligados')
    payload = TeamsGatewayMessageRequest(
        destino_tipo='chat',
        destino_id='fulano@tieri659.onmicrosoft.com',
        texto='Ola',
        modo='flow_bot',
        permitir_fallback=False,
    )

    resultado = _run(svc.enviar_mensagem_gateway(payload, db=db_session, correlation_id='corr-multi-2'))

    assert resultado['entregue'] is False
    assert resultado['motivo'] == 'flow_bot_todos_indisponiveis'
    assert len(resultado['provider_response']['tentativas']) == 2
    assert mock_enviar.await_count == 2


def test_flow_bot_alvos_cai_para_env_quando_sem_donos_no_banco(db_session, monkeypatch):
    monkeypatch.setattr(svc.settings, 'teams_flow_bot_webhook_url', 'https://exemplo.invalid/env-flow')

    alvos = svc._flow_bot_alvos(db_session)

    assert alvos == [('env:TEAMS_FLOW_BOT_WEBHOOK_URL', 'https://exemplo.invalid/env-flow')]
