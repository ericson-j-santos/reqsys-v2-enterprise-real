from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.service_tokens import require_admin_or_service_token
from app.db import get_db
from app.schemas.copilot_memory import CopilotMemoryBatchSyncRequest, PlannerSyncAckRequest
from app.services.copilot_memory import (
    confirmar_comando_planner,
    listar_comandos_planner,
    listar_historico,
    listar_memorias,
    resumo_memoria,
    sincronizar_lote,
)

router = APIRouter(prefix='/copilot-memory', tags=['Hub Low-Code & IA - Memória Copilot'])

require_copilot_memory_auth = require_admin_or_service_token('copilot_memory:sincronizar')


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
    """Lista memória persistente; formato também serve para projeção no Excel."""
    return ok({
        'items': listar_memorias(
            db,
            planner_task_id=planner_task_id,
            validade=validade,
            limit=limit,
        )
    })


@router.get('/export')
def copilot_memory_export(
    db: Session = Depends(get_db),
    validade: str | None = Query(default=None),
    limit: int = Query(default=2000, ge=1, le=5000),
    _auth=Depends(require_copilot_memory_auth),
):
    """Projeção tabular para o flow ReqSys -> Excel/SharePoint."""
    items = listar_memorias(db, validade=validade, limit=limit)
    return ok({'items': items, 'total': len(items)})


@router.get('/summary')
def copilot_memory_summary(
    db: Session = Depends(get_db),
    _auth=Depends(require_copilot_memory_auth),
):
    """Indicadores operacionais para dashboard e monitoramento do flow."""
    return ok(resumo_memoria(db))


@router.get('/planner-commands')
def copilot_memory_planner_commands(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    _auth=Depends(require_copilot_memory_auth),
):
    """Comandos Excel -> Planner explicitamente autorizados e ainda pendentes."""
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
    """Confirma sucesso/falha da ação Update task executada no Power Automate."""
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
    """Histórico versionado por mudança real de conteúdo."""
    return ok({'items': listar_historico(db, memory_id, limit=limit)})
