import logging

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
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
from app.services.teams_flow_bot_provisioning import (
    buscar_flows_por_nome,
    clonar_flow_para_novo_dono,
    listar_workflows_da_solution,
    promover_flow_para_ambiente,
)
from app.services.auditoria import registrar_evento
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


@router.post('/bot/messages')
async def teams_gateway_bot_messages(request: Request, db: Session = Depends(get_db)):
    """Webhook de entrada do Bot Framework (Teams).

    Valida o JWT assinado enviado pelo Bot Framework no header Authorization e,
    quando a activity traz um usuario/AAD object id identificavel, persiste a
    conversationReference — unico jeito de o gateway enviar mensagem proativa
    depois, sem exigir login interativo do usuario a cada envio.
    """
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
    """Cadastra um novo dono/backup do canal flow_bot (webhook de um flow ja autorizado)."""
    item = criar_flow_bot_owner(db, payload)
    return ok(_serializar_flow_bot_owner(item))


@router.patch('/flow-bot/owners/{owner_id}', dependencies=[Depends(require_admin)])
def teams_gateway_flow_bot_owners_atualizar(owner_id: int, payload: TeamsFlowBotOwnerUpdate, db: Session = Depends(get_db)):
    """Atualiza prioridade/ativo/webhook_url/observacao de um dono do canal flow_bot."""
    try:
        item = atualizar_flow_bot_owner(db, owner_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ok(_serializar_flow_bot_owner(item))


@router.delete('/flow-bot/owners/{owner_id}', dependencies=[Depends(require_admin)])
def teams_gateway_flow_bot_owners_remover(owner_id: int, db: Session = Depends(get_db)):
    """Remove um dono/backup do canal flow_bot."""
    try:
        remover_flow_bot_owner(db, owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ok({'removido': True, 'id': owner_id})


@router.get('/flow-bot/flows', dependencies=[Depends(require_admin)])
async def teams_gateway_flow_bot_buscar_flows(environment: str, nome_contem: str):
    """Lista cloud flows cujo nome contem `nome_contem`, com status e data de
    modificacao — resolve ambiguidade entre flows/versoes com nomes parecidos
    (ex.: `robo_envia_teams_v2.0.1`, `robo_envia_teams20260108v2`) sem precisar
    adivinhar no portal.
    """
    try:
        itens = await buscar_flows_por_nome(environment, nome_contem)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f'Falha na Dataverse API: HTTP {exc.response.status_code}') from None
    return ok({'items': itens})


@router.get('/flow-bot/solutions/{solution_name}/flows', dependencies=[Depends(require_admin)])
async def teams_gateway_flow_bot_solution_flows(solution_name: str, environment: str):
    """Lista os cloud flows que estao DE FATO empacotados numa Solution
    especifica — resposta definitiva (via `solutioncomponents`), nao um palpite
    pelo nome.
    """
    try:
        itens = await listar_workflows_da_solution(environment, solution_name)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f'Falha na Dataverse API: HTTP {exc.response.status_code}') from None
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ok({'items': itens})


@router.post('/flow-bot/clonar-flow', dependencies=[Depends(require_admin)])
async def teams_gateway_flow_bot_clonar_flow(payload: TeamsFlowBotClonarFlowRequest):
    """Clona a definicao de um flow ja existente (Post as: Flow bot / Chat with Flow
    bot) para um novo dono, reaproveitando o mesmo trigger/acao — evita
    reconfigurar manualmente cada backup no designer do Power Automate.

    Pre-requisito manual e inevitavel: o novo dono precisa ja ter autorizado a
    propria conexao Teams uma vez (Microsoft nao permite client-credentials
    nesse conector); informe o `nova_connection_id` dela. Nao cria a conexao,
    so clona a definicao do flow.
    """
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
