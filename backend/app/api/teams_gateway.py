from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.db import get_db
from app.schemas.teams_gateway import TeamsGatewayMessageRequest
from app.services.teams_gateway import (
    enviar_mensagem_gateway,
    selecionar_rota,
    status_gateway,
)

router = APIRouter(prefix='/v1/teams-gateway', tags=['Teams Messaging Gateway'])


@router.get('/status')
def teams_gateway_status(db: Session = Depends(get_db)):
    """Retorna rotas disponiveis, politica de roteamento e pendencias de configuracao."""
    return ok(status_gateway(db))


@router.post('/routes')
def teams_gateway_routes(payload: TeamsGatewayMessageRequest, db: Session = Depends(get_db)):
    """Simula a rota escolhida para uma mensagem sem executar envio externo."""
    return ok(selecionar_rota(payload, db))


@router.post('/messages')
async def teams_gateway_messages(
    payload: TeamsGatewayMessageRequest,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Gateway robusto de mensageria Teams.

    - chat humano: usa Graph delegado com usuario_access_token;
    - automacao/canal: usa webhook quando configurado;
    - graph_app_only: apenas quando explicitamente solicitado;
    - bot: rota futura, anunciada em /status.
    """
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    result = await enviar_mensagem_gateway(payload, db=db, correlation_id=correlation_id)
    return ok(result, result['correlation_id'])


@router.post('/messages/delegated')
async def teams_gateway_messages_delegated(
    payload: TeamsGatewayMessageRequest,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Atalho explicito para Graph delegado."""
    payload.modo = 'graph_delegado'
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    result = await enviar_mensagem_gateway(payload, db=db, correlation_id=correlation_id)
    return ok(result, result['correlation_id'])


@router.post('/messages/webhook')
async def teams_gateway_messages_webhook(
    payload: TeamsGatewayMessageRequest,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Atalho explicito para webhook/canal operacional."""
    payload.modo = 'webhook'
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    result = await enviar_mensagem_gateway(payload, db=db, correlation_id=correlation_id)
    return ok(result, result['correlation_id'])
