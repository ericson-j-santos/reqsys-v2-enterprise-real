import logging

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.core.service_tokens import ServiceAuthContext, require_admin_or_service_token
from app.db import get_db
from app.schemas.teams_gateway import (
    TeamsFlowBotClonarFlowRequest,
    TeamsFlowBotOwnerCreate,
    TeamsFlowBotOwnerUpdate,
    TeamsFlowBotPromoverSolutionRequest,
    TeamsGatewayMessageRequest,
)
from app.schemas.teams_recipient_policy import (
    TeamsNotificationRecipientCreate,
    TeamsNotificationRecipientUpdate,
    TeamsRecipientPolicyMessageRequest,
)
from app.services.auditoria import registrar_evento
from app.services.teams_flow_bot_provisioning import (
    buscar_flows_por_nome,
    clonar_flow_para_novo_dono,
    listar_workflows_da_solution,
    promover_flow_para_ambiente,
)
from app.services.teams_gateway import (
    atualizar_flow_bot_owner,
    criar_flow_bot_owner,
    enviar_mensagem_gateway,
    listar_flow_bot_owners,
    remover_flow_bot_owner,
    salvar_conversa_referencia_bot,
    selecionar_rota,
    status_gateway,
    validar_jwt_bot_framework,
)
from app.services.teams_recipient_policy import (
    atualizar_destinatario,
    criar_destinatario,
    enviar_mensagem_por_politica,
    listar_destinatarios,
    remover_destinatario,
)

logger = logging.getLogger('reqsys.teams_gateway_api')

router = APIRouter(prefix='/v1/teams-gateway', tags=['Teams Messaging Gateway'])

# Instancia unica (nao recriada por request) para permitir override em testes
# via app.dependency_overrides — ver require_admin_or_service_token.
require_promover_solution_auth = require_admin_or_service_token('teams_gateway:promover_solution')


def _serializar_flow_bot_owner(item) -> dict:
    return {
        'id': item.id,
        'owner_email': item.owner_email,
        'prioridade': item.prioridade,
        'ativo': item.ativo,
        'observacao': item.observacao,
        'webhook_configurado': bool(item.webhook_url),
        'criado_em': item.criado_em.isoformat() if item.criado_em else None,
        'atualizado_em': item.atualizado_em.isoformat() if item.atualizado_em else None,
    }


def _serializar_destinatario(item) -> dict:
    return {
        'id': item.id,
        'politica': item.politica,
        'nome': item.nome,
        'destino_id': item.destino_id,
        'destino_tipo': item.destino_tipo,
        'prioridade': item.prioridade,
        'ativo': item.ativo,
        'observacao': item.observacao,
        'criado_em': item.criado_em.isoformat() if item.criado_em else None,
        'atualizado_em': item.atualizado_em.isoformat() if item.atualizado_em else None,
    }


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
    """Gateway robusto de mensageria Teams."""
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    result = await enviar_mensagem_gateway(payload, db=db, correlation_id=correlation_id)
    return ok(result, result['correlation_id'])


@router.post('/recipient-policies/{politica}/messages')
async def teams_gateway_recipient_policy_messages(
    politica: str,
    payload: TeamsRecipientPolicyMessageRequest,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Resolve destinatarios ativos no banco e envia conforme a politica solicitada."""
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    result = await enviar_mensagem_por_politica(
        politica,
        payload,
        db=db,
        correlation_id=correlation_id,
    )
    return ok(result, result['correlation_id'])


@router.get('/recipient-policies/recipients', dependencies=[Depends(require_admin)])
def teams_gateway_recipients_listar(
    politica: str | None = None,
    apenas_ativos: bool = False,
    db: Session = Depends(get_db),
):
    itens = listar_destinatarios(db, politica, apenas_ativos=apenas_ativos)
    return ok({'items': [_serializar_destinatario(item) for item in itens]})


@router.post('/recipient-policies/recipients', dependencies=[Depends(require_admin)])
def teams_gateway_recipients_criar(
    payload: TeamsNotificationRecipientCreate,
    db: Session = Depends(get_db),
):
    try:
        item = criar_destinatario(db, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Destinatario ja cadastrado nesta politica.') from None
    return ok(_serializar_destinatario(item))


@router.patch('/recipient-policies/recipients/{recipient_id}', dependencies=[Depends(require_admin)])
def teams_gateway_recipients_atualizar(
    recipient_id: int,
    payload: TeamsNotificationRecipientUpdate,
    db: Session = Depends(get_db),
):
    try:
        item = atualizar_destinatario(db, recipient_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Destinatario duplicado nesta politica.') from None
    return ok(_serializar_destinatario(item))


@router.delete('/recipient-policies/recipients/{recipient_id}', dependencies=[Depends(require_admin)])
def teams_gateway_recipients_remover(recipient_id: int, db: Session = Depends(get_db)):
    try:
        remover_destinatario(db, recipient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ok({'removido': True, 'id': recipient_id})


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


@router.post('/bot/messages')
async def teams_gateway_bot_messages(request: Request, db: Session = Depends(get_db)):
    """Webhook de entrada do Bot Framework (Teams)."""
    auth_header = request.headers.get('authorization', '')
    token = auth_header[7:].strip() if auth_header.lower().startswith('bearer ') else ''
    if not token:
        raise HTTPException(status_code=401, detail='Token do Bot Framework ausente')

    try:
        validar_jwt_bot_framework(token)
    except Exception:
        logger.warning('teams_gateway_bot_token_invalido')
        raise HTTPException(status_code=401, detail='Token do Bot Framework invalido') from None

    activity = await request.json()
    remetente = activity.get('from') or {}
    usuario_aad_object_id = remetente.get('aadObjectId')
    service_url = activity.get('serviceUrl')
    conversation_id = (activity.get('conversation') or {}).get('id')
    bot_id = (activity.get('recipient') or {}).get('id', '')
    tenant_id = ((activity.get('channelData') or {}).get('tenant') or {}).get('id', '')

    if usuario_aad_object_id and service_url and conversation_id:
        salvar_conversa_referencia_bot(
            db,
            usuario_aad_object_id=usuario_aad_object_id,
            service_url=service_url,
            conversation_id=conversation_id,
            bot_id=bot_id,
            tenant_id=tenant_id,
        )

    return ok({'type': 'message', 'recebido': True})


@router.get('/flow-bot/owners', dependencies=[Depends(require_admin)])
def teams_gateway_flow_bot_owners_listar(db: Session = Depends(get_db)):
    """Lista os donos/backups cadastrados do canal flow_bot, em ordem de prioridade."""
    itens = listar_flow_bot_owners(db)
    return ok({'items': [_serializar_flow_bot_owner(item) for item in itens]})


@router.post('/flow-bot/owners', dependencies=[Depends(require_admin)])
def teams_gateway_flow_bot_owners_criar(payload: TeamsFlowBotOwnerCreate, db: Session = Depends(get_db)):
    """Cadastra um novo dono/backup do canal flow_bot."""
    item = criar_flow_bot_owner(db, payload)
    return ok(_serializar_flow_bot_owner(item))


@router.patch('/flow-bot/owners/{owner_id}', dependencies=[Depends(require_admin)])
def teams_gateway_flow_bot_owners_atualizar(owner_id: int, payload: TeamsFlowBotOwnerUpdate, db: Session = Depends(get_db)):
    """Atualiza prioridade/ativo/webhook_url/observacao de um dono do flow_bot."""
    try:
        item = atualizar_flow_bot_owner(db, owner_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ok(_serializar_flow_bot_owner(item))


@router.delete('/flow-bot/owners/{owner_id}', dependencies=[Depends(require_admin)])
def teams_gateway_flow_bot_owners_remover(owner_id: int, db: Session = Depends(get_db)):
    """Remove um dono/backup cadastrado do canal flow_bot."""
    try:
        remover_flow_bot_owner(db, owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ok({'removido': True, 'id': owner_id})


@router.get('/flow-bot/flows', dependencies=[Depends(require_admin)])
async def teams_gateway_flow_bot_buscar_flows(environment: str, nome_contem: str):
    """Lista cloud flows cujo nome contem `nome_contem`."""
    try:
        itens = await buscar_flows_por_nome(environment, nome_contem)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f'Falha na Dataverse API: HTTP {exc.response.status_code}') from None
    return ok({'items': itens})


@router.get('/flow-bot/solutions/{solution_name}/flows', dependencies=[Depends(require_admin)])
async def teams_gateway_flow_bot_solution_flows(solution_name: str, environment: str):
    """Lista cloud flows empacotados numa Solution especifica."""
    try:
        itens = await listar_workflows_da_solution(environment, solution_name)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f'Falha na Dataverse API: HTTP {exc.response.status_code}') from None
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ok({'items': itens})


@router.post('/flow-bot/clonar-flow', dependencies=[Depends(require_admin)])
async def teams_gateway_flow_bot_clonar_flow(payload: TeamsFlowBotClonarFlowRequest):
    """Clona um flow existente para um novo dono."""
    try:
        resultado = await clonar_flow_para_novo_dono(
            environment=payload.environment,
            flow_id_origem=payload.flow_id_origem,
            nova_connection_id=payload.nova_connection_id,
            novo_display_name=payload.novo_display_name,
            connection_reference_key=payload.connection_reference_key,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f'Falha na Flow API: HTTP {exc.response.status_code}') from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return ok(resultado)


@router.post('/flow-bot/promover-solution')
async def teams_gateway_flow_bot_promover_solution(
    payload: TeamsFlowBotPromoverSolutionRequest,
    ctx: ServiceAuthContext = Depends(require_promover_solution_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """Promove o flow_bot de um ambiente para outro via Power Platform Solutions
    (Dataverse ExportSolution/ImportSolution — API 100% documentada, diferente
    da Flow Management API bruta usada em `/flow-bot/clonar-flow`).

    Uso: promover dev → test → prod. NAO serve para criar donos de backup no
    MESMO ambiente (Solutions casam componentes por unique name; reimportar a
    mesma solution no mesmo ambiente atualiza o flow existente, nao cria um
    irmao novo) — para isso use `/flow-bot/clonar-flow`.

    Pre-requisito manual e inevitavel: o dono do ambiente-alvo precisa ja ter
    autorizado a propria conexao Teams la; informe o `connection_id_destino`.

    Autenticação: JWT admin (humano) OU `X-Service-Token` escopado para
    `teams_gateway:promover_solution` (automação — ver app/core/service_tokens.py).
    """
    correlation_id = x_correlation_id or resolver_correlation_id()
    registrar_evento(
        db, correlation_id, ctx.ator, 'TEAMS_FLOW_BOT_PROMOCAO_INICIADA', 'teams_flow_bot_solution',
        payload.solution_name,
    )
    try:
        resultado = await promover_flow_para_ambiente(
            environment_url_origem=payload.environment_url_origem,
            environment_url_destino=payload.environment_url_destino,
            solution_name=payload.solution_name,
            connection_reference_logical_name=payload.connection_reference_logical_name,
            connection_id_destino=payload.connection_id_destino,
            novo_flow_display_name=payload.novo_flow_display_name,
            managed=payload.managed,
        )
    except httpx.HTTPStatusError as exc:
        registrar_evento(
            db, correlation_id, ctx.ator, 'TEAMS_FLOW_BOT_PROMOCAO_FALHA', 'teams_flow_bot_solution',
            payload.solution_name,
        )
        raise HTTPException(status_code=502, detail=f'Falha na Dataverse API: HTTP {exc.response.status_code}') from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    registrar_evento(
        db, correlation_id, ctx.ator, 'TEAMS_FLOW_BOT_PROMOCAO_CONCLUIDA', 'teams_flow_bot_solution',
        payload.solution_name,
    )
    return ok(resultado)
