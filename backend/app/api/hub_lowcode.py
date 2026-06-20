from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.schemas.planner import (
    PlannerDiscoveryRequest,
    PlannerPublishRequest,
    PlannerWebhookConfigRequest,
)
from app.services.hub_lowcode import (
    descobrir_planner_no_ambiente,
    listar_ambientes_powerplatform,
    listar_flows_pa,
    listar_historico_integracoes,
    listar_pacotes_ia,
    listar_runs_github,
    obter_planner_webhook_config,
    publicar_tarefas_planner,
    salvar_log_integracao,
    salvar_planner_webhook_config,
    status_consolidado,
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
    """Flows Power Automate e ultimas execucoes do flow ReqSys - Criar no Planner."""
    return ok(await listar_flows_pa())


@router.get('/powerplatform/ambientes')
async def hub_powerplatform_ambientes():
    """Lista ambientes Power Platform disponiveis para configurar o Flow Planner."""
    return ok(await listar_ambientes_powerplatform())


@router.post('/planner/descobrir')
async def hub_descobrir_planner(payload: PlannerDiscoveryRequest):
    """Lista flows candidatos e conexoes Planner em um ambiente Power Platform."""
    return ok(await descobrir_planner_no_ambiente(payload.instance_url, payload.filtro))


@router.get('/planner/webhook-config')
async def hub_planner_webhook_config(db: Session = Depends(get_db)):
    """Mostra se o webhook Planner esta configurado, sem expor o segredo completo."""
    config = obter_planner_webhook_config(db)
    return ok({k: v for k, v in config.items() if k not in {'url', 'key'}})


@router.post('/planner/webhook-config')
async def hub_salvar_planner_webhook_config(payload: PlannerWebhookConfigRequest, db: Session = Depends(get_db)):
    """Salva a URL do trigger HTTP do Power Automate para uso pelo usuario final."""
    try:
        return ok(salvar_planner_webhook_config(db, payload.webhook_url, payload.webhook_key))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post('/planner/tasks')
async def hub_publicar_tarefas_planner(payload: PlannerPublishRequest, request: Request, db: Session = Depends(get_db)):
    """Publica tarefas da Task Console no Flow ReqSys - Criar no Planner e notifica o Teams."""
    correlation_id = request.headers.get('X-Correlation-Id')
    webhook_config = obter_planner_webhook_config(db)
    try:
        resultado = await publicar_tarefas_planner(
            payload.tarefas,
            payload.autor,
            correlation_id,
            webhook_url=webhook_config['url'],
            webhook_key=webhook_config['key'],
        )
    except Exception as exc:
        salvar_log_integracao(
            db, tipo='planner_task', status='erro',
            titulo=f'{len(payload.tarefas)} tarefa(s)',
            autor=payload.autor, total=len(payload.tarefas),
            mensagem=str(exc), correlation_id=correlation_id or '',
        )
        raise HTTPException(status_code=502, detail=f'Falha ao acionar Flow Planner: {exc}') from exc

    status_log = 'ok' if resultado.get('enviado') else 'skip'
    salvar_log_integracao(
        db, tipo='planner_task', status=status_log,
        titulo=f'{len(payload.tarefas)} tarefa(s) enviada(s)',
        autor=payload.autor, total=len(payload.tarefas),
        mensagem=resultado.get('mensagem', ''),
        detalhes={
            'flow': resultado.get('flow'),
            'resposta_flow': resultado.get('resposta_flow'),
            'teams_notificado': resultado.get('teams_notificado', False),
        },
        correlation_id=correlation_id or '',
    )
    return ok(resultado)


@router.get('/integracoes/historico')
async def hub_historico_integracoes(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    """Historico de eventos: tarefas Planner enviadas e notificacoes Teams."""
    return ok(listar_historico_integracoes(db, limit))


@router.get('/github')
async def hub_github(limit: int = Query(default=10, ge=1, le=50)):
    """Ultimas execucoes do GitHub Actions no repo ALM."""
    return ok(await listar_runs_github(limit))
