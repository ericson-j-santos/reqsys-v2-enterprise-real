import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.service_tokens import require_admin_or_service_token
from app.db import get_db
from app.schemas.copilot_memory import (
    CopilotMemoryBatchSyncRequest,
    CopilotMemoryInstallRequest,
    CopilotMemoryLowCodePackageRequest,
    PlannerSyncAckRequest,
)
from app.services.copilot_memory import (
    confirmar_comando_planner,
    listar_comandos_planner,
    listar_historico,
    listar_memorias,
    resumo_memoria,
    sincronizar_lote,
)
from app.services.copilot_memory_install_assistant import (
    criar_planilha_excel_grupo,
    despachar_implantacao,
    listar_arquivos_excel_grupo,
    listar_conexoes_instalacao,
    listar_planos_instalacao,
    status_assistente_instalacao,
)
from app.services.copilot_memory_install_safety import validar_destino_assistente
from app.services.copilot_memory_simple_factory import (
    gerar_copilot_memory_simple_solution,
)

router = APIRouter(prefix='/copilot-memory', tags=['Hub Low-Code & IA - Memória Copilot'])

require_copilot_memory_auth = require_admin_or_service_token('copilot_memory:sincronizar')


@router.post('/lowcode/package')
def copilot_memory_lowcode_package(
    payload: CopilotMemoryLowCodePackageRequest,
    _auth=Depends(require_copilot_memory_auth),
):
    """Gera um único pacote corporativo; não executa escrita no tenant."""
    solution = gerar_copilot_memory_simple_solution(payload)
    return ok(solution, solution['correlation_id'])


@router.get('/install/status')
async def copilot_memory_install_status(_auth=Depends(require_copilot_memory_auth)):
    """Retorna prontidão do assistente sem expor credenciais."""
    return ok(await status_assistente_instalacao())


@router.get('/install/plans')
async def copilot_memory_install_plans(
    group_id: str = Query(..., min_length=5, max_length=120),
    _auth=Depends(require_copilot_memory_auth),
):
    return ok(await listar_planos_instalacao(group_id))


@router.get('/install/files')
async def copilot_memory_install_files(
    group_id: str = Query(..., min_length=5, max_length=120),
    _auth=Depends(require_copilot_memory_auth),
):
    return ok(await listar_arquivos_excel_grupo(group_id))


@router.post('/install/workbook')
async def copilot_memory_install_workbook(
    group_id: str = Query(..., min_length=5, max_length=120),
    nome: str = Query(default='CopilotMemory.xlsx', min_length=5, max_length=120),
    _auth=Depends(require_copilot_memory_auth),
):
    """Cria a planilha padrão no drive do grupo; falha fechado se o tenant bloquear escrita."""
    try:
        return ok(await criar_planilha_excel_grupo(group_id, nome))
    except (ValueError, httpx.HTTPStatusError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get('/install/connections')
async def copilot_memory_install_connections(
    environment_id: str = Query(..., min_length=2, max_length=120),
    _auth=Depends(require_copilot_memory_auth),
):
    return ok(await listar_conexoes_instalacao(environment_id))


@router.post('/install/deploy')
async def copilot_memory_install_deploy(
    payload: CopilotMemoryInstallRequest,
    _auth=Depends(require_copilot_memory_auth),
):
    """Valida o destino e despacha as três definições completas via ALM/PAC CLI."""
    try:
        await validar_destino_assistente(payload.environment_id, payload.environment_url)
        result = await despachar_implantacao(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(result, result.get('correlation_id'))


@router.post('/sync')
def copilot_memory_sync(
    payload: CopilotMemoryBatchSyncRequest,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    _auth=Depends(require_copilot_memory_auth),
):
    """Upsert idempotente vindo de Planner, Excel, ReqSys, Copilot ou pesquisa."""
    correlation_id = resolver_correlation_id(x_correlation_id, payload.correlation_id)
    try:
        resultado = sincronizar_lote(
            db,
            [item.model_dump(by_alias=False) for item in payload.items],
            correlation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(resultado, correlation_id)


@router.get('/items')
def copilot_memory_items(
    db: Session = Depends(get_db),
    planner_task_id: str | None = Query(default=None),
    validade: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    _auth=Depends(require_copilot_memory_auth),
):
    return ok({'items': listar_memorias(db, planner_task_id=planner_task_id, validade=validade, limit=limit)})


@router.get('/export')
def copilot_memory_export(
    db: Session = Depends(get_db),
    validade: str | None = Query(default=None),
    limit: int = Query(default=2000, ge=1, le=5000),
    _auth=Depends(require_copilot_memory_auth),
):
    items = listar_memorias(db, validade=validade, limit=limit)
    return ok({'items': items, 'total': len(items)})


@router.get('/summary')
def copilot_memory_summary(
    db: Session = Depends(get_db),
    _auth=Depends(require_copilot_memory_auth),
):
    return ok(resumo_memoria(db))


@router.get('/planner-commands')
def copilot_memory_planner_commands(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    _auth=Depends(require_copilot_memory_auth),
):
    items = listar_comandos_planner(db, limit=limit)
    return ok({'items': items, 'total': len(items)})


@router.post('/{memory_id}/planner-ack')
def copilot_memory_planner_ack(
    memory_id: str,
    payload: PlannerSyncAckRequest,
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    _auth=Depends(require_copilot_memory_auth),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        item = confirmar_comando_planner(
            db,
            memory_id,
            sucesso=payload.sucesso,
            correlation_id=correlation_id,
            planner_task_id=payload.planner_task_id,
            erro=payload.erro,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, correlation_id)


@router.get('/{memory_id}/history')
def copilot_memory_history(
    memory_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    _auth=Depends(require_copilot_memory_auth),
):
    return ok({'items': listar_historico(db, memory_id, limit=limit)})
