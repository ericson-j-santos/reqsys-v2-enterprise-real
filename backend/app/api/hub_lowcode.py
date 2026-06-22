from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.services.hub_lowcode import (
    descobrir_planos_planner,
    listar_ambientes_powerplatform,
    listar_flows_pa,
    listar_historico_integracoes,
    listar_pacotes_ia,
    listar_runs_github,
    obter_planner_webhook_config,
    publicar_tarefas_planner,
    salvar_planner_webhook_config,
    status_consolidado,
    testar_teams_webhook,
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
