from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.core.security import get_current_user, require_admin
from app.db import get_db
from app.models.teams_notification_queue import TeamsNotificationQueueItem
from app.schemas.teams_notifications import TeamsNotificationEnqueueRequest
from app.services.teams_notifications import (
    criar_item_fila,
    executar_item_fila,
    listar_dlq,
    listar_fila,
    listar_logs,
    obter_dashboard,
    serializar_item,
)

router = APIRouter(prefix='/notificacoes', tags=['Teams Notification Control Center'])


@router.get('/dashboard', dependencies=[Depends(get_current_user)])
def dashboard_notificacoes(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    return ok(obter_dashboard(db, window_days=window_days))


@router.get('/fila', dependencies=[Depends(get_current_user)])
def fila_notificacoes(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    try:
        data = listar_fila(db, status=status, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return ok(data)


@router.get('/dlq', dependencies=[Depends(get_current_user)])
def dlq_notificacoes(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return ok(listar_dlq(db, limit=limit))


@router.get('/logs', dependencies=[Depends(get_current_user)])
def logs_notificacoes(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return ok(listar_logs(db, limit=limit))


@router.post('/enfileirar', dependencies=[Depends(require_admin)])
async def enfileirar_notificacao(
    payload: TeamsNotificationEnqueueRequest,
    db: Session = Depends(get_db),
):
    item = criar_item_fila(db, payload)
    if payload.enviar_agora:
        item = await executar_item_fila(db, item)
    return ok(serializar_item(item), item.correlation_id)


@router.post('/fila/processar/{id_evento}', dependencies=[Depends(require_admin)])
async def processar_notificacao(id_evento: int, db: Session = Depends(get_db)):
    item = db.get(TeamsNotificationQueueItem, id_evento)
    if item is None:
        raise HTTPException(status_code=404, detail='Evento de notificação não encontrado.')
    try:
        item = await executar_item_fila(db, item)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return ok(serializar_item(item), item.correlation_id)


@router.post('/dlq/reprocessar/{id_dlq}', dependencies=[Depends(require_admin)])
async def reprocessar_notificacao(id_dlq: int, db: Session = Depends(get_db)):
    item = db.get(TeamsNotificationQueueItem, id_dlq)
    if item is None or item.status_evento != 'FALHA':
        raise HTTPException(status_code=404, detail='Item não encontrado na DLQ.')
    try:
        item = await executar_item_fila(db, item)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return ok(serializar_item(item), item.correlation_id)
