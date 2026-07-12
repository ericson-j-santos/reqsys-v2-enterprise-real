from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.db import get_db
from app.schemas.lowcode_solution import LowCodeSolutionGenerateRequest
from app.services.hub_lowcode import (
    criar_chat_e_enviar_como_usuario,
    criar_chat_individual_teams,
    descobrir_planos_planner,
    enviar_mensagem_chat_teams,
    enviar_mensagem_chat_teams_como_usuario,
    listar_ambientes_powerplatform,
    listar_chats_como_usuario,
    listar_flows_pa,
    listar_historico_integracoes,
    listar_pacotes_ia,
    listar_runs_github,
    obter_planner_webhook_config,
    publicar_tarefas_planner,
    resumo_uso_flow_bot_hoje,
    salvar_log_integracao,
    salvar_planner_webhook_config,
    status_consolidado,
    testar_teams_webhook,
)
from app.services.lowcode_adr_coordinator import (
    listar_adr_base_coordenador,
    planejar_coordenacao_por_adr,
)
from app.services.lowcode_solution_factory import gerar_lowcode_solution
from app.services.power_automate_provisioning import (
    atualizar_status_provisionamento,
    despachar_workflow_provisionamento,
    gerar_manifesto_provisionamento_flow,
    listar_registry_provisionamentos,
    registrar_manifesto_provisionamento,
    resumo_registry_provisionamentos,
    serializar_registry,
)

router = APIRouter(prefix='/v1/hub-lowcode', tags=['Hub Low-Code & IA'])


@router.get('/status')
async def hub_status():
    """Resumo consolidado para o card do Dashboard."""
    return ok(await status_consolidado())


@router.get('/pacotes')
async def hub_pacotes(limit: int = Query(default=20, ge=1, le=100)):
    """Pacotes de contexto IA exportados (lista SharePoint IA_Catalogo_Projetos)."""
    return ok(await listar_pacotes_ia(limit))


@router.get('/flows')
async def hub_flows():
    """Flows Power Automate ativos via Dataverse."""
    return ok(await listar_flows_pa())


@router.get('/github')
async def hub_github(limit: int = Query(default=10, ge=1, le=50)):
    """Últimas execuções do GitHub Actions no repo ALM."""
    return ok(await listar_runs_github(limit))


@router.get('/powerplatform/ambientes')
async def hub_pp_ambientes():
    """Lista ambientes Power Platform via Management API."""
    return ok(await listar_ambientes_powerplatform())


# ---------------------------------------------------------------------------
# LowCode Solution Factory P0
# ---------------------------------------------------------------------------

@router.post('/solutions/generate')
def lowcode_solution_generate(payload: LowCodeSolutionGenerateRequest):
    """Gera blueprint completo de solution low-code sem executar escrita externa."""
    solution = gerar_lowcode_solution(payload)
    return ok(solution, solution['correlation_id'])


@router.post('/solutions/generate/canvas')
def lowcode_solution_generate_canvas(payload: LowCodeSolutionGenerateRequest):
    """Gera somente o canvas markdown da solution low-code."""
    solution = gerar_lowcode_solution(payload)
    return ok(
        {
            'solution_name': solution['solution_name'],
            'display_name': solution['display_name'],
            'target_environment': solution['target_environment'],
            'canvas_markdown': solution['canvas_markdown'],
            'canvas_app': solution['apps']['canvas_app'],
        },
        solution['correlation_id'],
    )


# ---------------------------------------------------------------------------
# LowCode ADR Agent Coordinator P0
# ---------------------------------------------------------------------------

@router.get('/agents/coordenador/adr-base')
def lowcode_adr_agent_base():
    """Retorna a base governada de ADRs e agentes do Coordenador ReqSys."""
    return ok(listar_adr_base_coordenador())


@router.post('/agents/coordenador/planejar')
def lowcode_adr_agent_planejar(
    objetivo: str = Body(..., min_length=10, max_length=2000),
    adr_refs: list[str] | None = Body(default=None),
    dry_run: bool = Body(default=True),
    x_correlation_id: str | None = Header(default=None),
):
    """Planeja a chamada de agentes especializados conforme ADR aplicável.

    O endpoint opera em modo governado: por padrão não executa escrita externa, apenas
    devolve o plano de roteamento, guardrails, rastreabilidade e critérios de aceite.
    """
    plano = planejar_coordenacao_por_adr(
        objetivo=objetivo,
        adr_refs=adr_refs,
        dry_run=dry_run,
        correlation_id=x_correlation_id,
    )
    return ok(plano, plano['correlation_id'])


# ---------------------------------------------------------------------------
# Power Automate Flow Provisioning P0/P0.1
# ---------------------------------------------------------------------------

@router.post('/power-automate/flows/provisioning-plan')
def power_automate_flow_provisioning_plan(
    db: Session = Depends(get_db),
    display_name: str = Body(..., min_length=5),
    trigger_type: str = Body(default='HttpRequest'),
    description: str = Body(default=''),
    target_environment: str = Body(default='dev'),
    solution_name: str = Body(default='ReqSysAutomacao'),
    dry_run: bool = Body(default=True),
    registrar: bool = Body(default=True),
    x_correlation_id: str | None = Header(default=None),
):
    """Gera manifesto governado para criar flow via ALM/PAC CLI."""
    manifesto = gerar_manifesto_provisionamento_flow(
        display_name=display_name,
        trigger_type=trigger_type,
        description=description,
        target_environment=target_environment,
        solution_name=solution_name,
        correlation_id=x_correlation_id,
        dry_run=dry_run,
    )
    registry = registrar_manifesto_provisionamento(db, manifesto, status='planned') if registrar else None
    return ok({'manifesto': manifesto, 'registry': serializar_registry(registry) if registry else None}, manifesto['correlation_id'])


@router.post('/power-automate/flows/provision')
async def power_automate_flow_provision(
    db: Session = Depends(get_db),
    display_name: str = Body(..., min_length=5),
    trigger_type: str = Body(default='HttpRequest'),
    description: str = Body(default=''),
    target_environment: str = Body(default='dev'),
    solution_name: str = Body(default='ReqSysAutomacao'),
    x_correlation_id: str | None = Header(default=None),
):
    """Solicita dispatch do workflow ALM que provisiona o flow.

    Se GITHUB_PAT nao estiver configurado, retorna plano e motivo sem falhar.
    """
    manifesto = gerar_manifesto_provisionamento_flow(
        display_name=display_name,
        trigger_type=trigger_type,
        description=description,
        target_environment=target_environment,
        solution_name=solution_name,
        correlation_id=x_correlation_id,
        dry_run=False,
    )
    dispatch = await despachar_workflow_provisionamento(manifesto)
    status_registry = 'dispatched' if dispatch.get('dispatched') else 'pending_configuration'
    registry = registrar_manifesto_provisionamento(db, manifesto, status=status_registry, dispatch=dispatch)
    salvar_log_integracao(
        db,
        tipo='power_automate_flow_provisioning',
        status='solicitado' if dispatch.get('dispatched') else 'pendente',
        autor='reqsys',
        titulo=display_name,
        mensagem='Provisionamento de flow Power Automate solicitado via ALM',
        detalhes={'manifesto': manifesto, 'dispatch': dispatch, 'registry_id': registry.id},
        correlation_id=manifesto['correlation_id'],
    )
    return ok({'manifesto': manifesto, 'dispatch': dispatch, 'registry': serializar_registry(registry)}, manifesto['correlation_id'])


@router.get('/power-automate/flows/provisioning-registry')
def power_automate_flow_provisioning_registry(
    db: Session = Depends(get_db),
    ambiente: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Lista provisionamentos registrados com filtros operacionais."""
    return ok({'items': listar_registry_provisionamentos(db, ambiente=ambiente, status=status, limit=limit)})


@router.get('/power-automate/flows/provisioning-registry/summary')
def power_automate_flow_provisioning_registry_summary(db: Session = Depends(get_db)):
    """Resumo executivo para Ops Dashboard / Strategic Governance."""
    return ok(resumo_registry_provisionamentos(db))


@router.patch('/power-automate/flows/provisioning-registry/{correlation_id}/status')
def power_automate_flow_provisioning_registry_status(
    correlation_id: str,
    db: Session = Depends(get_db),
    status: str = Body(...),
    workflow_run_url: str | None = Body(default=None),
    artifact_url: str | None = Body(default=None),
    erro: str | None = Body(default=None),
):
    """Atualiza status operacional de um provisionamento por correlation_id."""
    try:
        item = atualizar_status_provisionamento(
            db,
            correlation_id=correlation_id,
            status=status,
            workflow_run_url=workflow_run_url,
            artifact_url=artifact_url,
            erro=erro,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(serializar_registry(item), correlation_id)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

@router.get('/planner/webhook-config')
def planner_webhook_config(db: Session = Depends(get_db)):
    """Retorna a configuração atual do webhook (sem expor a chave)."""
    cfg = obter_planner_webhook_config(db)
    return ok({
        'configurado': cfg['configurado'],
        'teams_configurado': cfg['teams_configurado'],
        'webhook_url_preview': (cfg.get('webhook_url') or '')[:60] + '...' if cfg.get('webhook_url') else '',
    })


@router.put('/planner/webhook-config')
def planner_webhook_config_update(
    db: Session = Depends(get_db),
    webhook_url: str | None = Body(default=None),
    webhook_key: str | None = Body(default=None),
    teams_webhook_url: str | None = Body(default=None),
):
    """Atualiza URL/chave do webhook do Planner e/ou URL do Teams Incoming Webhook."""
    return ok(salvar_planner_webhook_config(db, webhook_url, webhook_key, teams_webhook_url))


@router.post('/planner/tasks')
async def planner_publicar_tarefas(
    db: Session = Depends(get_db),
    tarefas_texto: str = Body(..., description='Linhas: Titulo|Resp|Data|Bucket|Prioridade|Desc'),
    autor: str = Body(default=''),
    correlation_id: str | None = Body(default=None),
):
    """
    Publica tarefas no Planner via Power Automate flow HTTP.
    Retorna: { ok, criadas, teams_notificado, correlation_id }.
    """
    return ok(await publicar_tarefas_planner(db, tarefas_texto, autor, correlation_id))


@router.get('/planner/descobrir')
async def planner_descobrir(group_id: str = Query(..., description='ID do grupo M365')):
    """Lista planos Planner do grupo via Graph API."""
    return ok(await descobrir_planos_planner(group_id))


# ---------------------------------------------------------------------------
# Teams webhook
# ---------------------------------------------------------------------------

@router.post('/teams/testar-webhook')
async def teams_testar(
    db: Session = Depends(get_db),
    teams_webhook_url: str | None = Body(default=None),
):
    """Envia mensagem de teste ao webhook Teams configurado (ou à URL fornecida)."""
    url = teams_webhook_url
    if not url:
        cfg = obter_planner_webhook_config(db)
        url = cfg.get('teams_webhook_url') or ''
    return ok(await testar_teams_webhook(url))


# ---------------------------------------------------------------------------
# Teams via Graph API — mensagens em chat 1:1/grupo
#
# O Graph bloqueia o envio de mensagem app-only para chats entre humanos (403
# exigindo Teamwork.Migrate.All, validado ao vivo em 2026-07-07) — por isso o
# envio real usa o fluxo delegado (.../mensagens/chat-delegado), que recebe o
# access_token do Graph já adquirido pelo frontend com o usuário logado
# (escopo ChatMessage.Send/Chat.ReadWrite, já consentido no tenant). O endpoint
# app-only (.../mensagens/chat) fica mantido só para cenários futuros onde o
# próprio app seja participante do chat (ex.: Teams App/bot instalado).
# ---------------------------------------------------------------------------

@router.get('/teams/graph/status')
def teams_graph_status():
    """Indica se a mensageria Teams via Graph API está configurada (ADR-007/009)."""
    envio_configurado = settings.teams_graph_configurado
    criacao_configurada = settings.teams_graph_chat_criacao_configurada
    return ok({
        'envio_app_only_configurado': envio_configurado,
        'criacao_de_chat_1a1_configurada': criacao_configurada,
        'campos_faltantes': settings.teams_graph_missing_fields,
        'semaforo': 'verde' if envio_configurado else 'cinza',
        'nota': (
            'Envio app-only e bloqueado pelo Graph para chats entre humanos '
            '(403 Teamwork.Migrate.All) — use /mensagens/chat-delegado com o '
            'access_token do usuário logado para enviar de fato.'
        ),
    })


@router.post('/teams/graph/mensagens/chat')
async def teams_graph_enviar_mensagem_chat(
    db: Session = Depends(get_db),
    chat_id: str = Body(..., min_length=1),
    texto: str = Body(..., min_length=1, max_length=20000),
    content_type: str = Body(default='text'),
    autor: str = Body(default=''),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Envia mensagem app-only via Microsoft Graph a um chat existente do Teams.

    Aviso: falha com 403 para chats entre humanos (limitação do Graph, não da
    configuração). Para enviar de fato, use /teams/graph/mensagens/chat-delegado.
    """
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    resultado = await enviar_mensagem_chat_teams(
        chat_id, texto, content_type=content_type, db=db, autor=autor, correlation_id=correlation_id,
    )
    return ok(resultado, correlation_id)


@router.post('/teams/graph/mensagens/chat-delegado')
async def teams_graph_enviar_mensagem_chat_delegado(
    db: Session = Depends(get_db),
    chat_id: str = Body(..., min_length=1),
    texto: str = Body(..., min_length=1, max_length=20000),
    usuario_access_token: str = Body(..., min_length=1),
    content_type: str = Body(default='text'),
    autor: str = Body(default=''),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Envia mensagem a um chat existente usando o access_token delegado do
    usuário logado (adquirido pelo frontend com escopo ChatMessage.Send/
    Chat.ReadWrite). Caminho recomendado — funciona para chats humano-humano.
    """
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    resultado = await enviar_mensagem_chat_teams_como_usuario(
        chat_id, texto, usuario_access_token,
        content_type=content_type, db=db, autor=autor, correlation_id=correlation_id,
    )
    return ok(resultado, correlation_id)


@router.post('/teams/graph/chats')
async def teams_graph_listar_chats(
    usuario_access_token: str = Body(..., min_length=1, embed=True),
    top: int = Body(default=50, ge=1, le=200, embed=True),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Lista os chats (1:1/grupo) do usuário logado via Graph (access_token
    delegado), para o frontend oferecer um seletor em vez de exigir chat_id
    manual. Usa o mesmo escopo Chat.ReadWrite já concedido — sem permissão nova.
    """
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    resultado = await listar_chats_como_usuario(usuario_access_token, top=top)
    return ok(resultado, correlation_id)


@router.post('/teams/graph/chats/individual')
async def teams_graph_criar_chat_individual(
    usuario_a_aad_object_id: str = Body(..., min_length=1),
    usuario_b_aad_object_id: str = Body(..., min_length=1),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Cria (ou obtém) um chat 1:1 app-only entre dois usuários AAD reais, sem
    enviar mensagem (a criação funciona app-only; o envio exige o fluxo delegado).
    """
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    resultado = await criar_chat_individual_teams(usuario_a_aad_object_id, usuario_b_aad_object_id, correlation_id=correlation_id)
    return ok(resultado, correlation_id)


@router.post('/teams/graph/chats/individual/enviar-delegado')
async def teams_graph_criar_chat_e_enviar_delegado(
    db: Session = Depends(get_db),
    usuario_a_aad_object_id: str = Body(..., min_length=1),
    usuario_b_aad_object_id: str = Body(..., min_length=1),
    texto: str = Body(..., min_length=1, max_length=20000),
    usuario_access_token: str = Body(..., min_length=1),
    content_type: str = Body(default='text'),
    autor: str = Body(default=''),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    """Cria (ou obtém) o chat 1:1 entre os dois usuários (app-only) e envia a
    mensagem usando o access_token delegado do usuário logado.
    """
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    resultado = await criar_chat_e_enviar_como_usuario(
        usuario_a_aad_object_id, usuario_b_aad_object_id, texto, usuario_access_token,
        content_type=content_type, db=db, autor=autor, correlation_id=correlation_id,
    )
    return ok(resultado, correlation_id)


# ---------------------------------------------------------------------------
# Histórico de integrações
# ---------------------------------------------------------------------------

@router.get('/integracoes/historico')
def integracoes_historico(
    db: Session = Depends(get_db),
    tipo: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Lista eventos de integração (Planner, Teams, etc.) com filtros opcionais.
    Usado pelo Painel de Integrações no frontend.
    """
    return ok(listar_historico_integracoes(db, tipo, status, limit))


@router.get('/integracoes/flow-bot/uso-hoje')
def integracoes_flow_bot_uso_hoje(db: Session = Depends(get_db)):
    """Resumo de uso diario do flow_bot por dono do Power Automate."""
    return ok(resumo_uso_flow_bot_hoje(db))
