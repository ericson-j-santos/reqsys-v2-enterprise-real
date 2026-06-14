from fastapi import APIRouter, Query

from app.core.envelope import ok
from app.services.hub_lowcode import (
    listar_flows_pa,
    listar_pacotes_ia,
    listar_runs_github,
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
    """Flows Power Automate e últimas execuções do flow ReqSys - Criar no Planner."""
    return ok(await listar_flows_pa())


@router.get('/github')
async def hub_github(limit: int = Query(default=10, ge=1, le=50)):
    """Últimas execuções do GitHub Actions no repo ALM."""
    return ok(await listar_runs_github(limit))
