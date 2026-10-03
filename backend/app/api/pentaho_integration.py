from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.core.service_tokens import ServiceAuthContext, require_admin_or_service_token
from app.db import get_db
from app.schemas.pentaho_integration import (
    PentahoLoteEntrada,
    PentahoLoteResposta,
    PentahoLoteStatus,
)
from app.services.pentaho_integration import (
    criar_ou_obter_lote,
    obter_dashboard,
    obter_lote,
    preparar_reprocessamento,
    processar_lote_assincrono,
    serializar_status,
)

router = APIRouter(prefix='/api/integracoes/pentaho', tags=['Integrações - Pentaho'])
_autorizar_pentaho = require_admin_or_service_token('pentaho:integracao')


@router.post('/lotes', response_model=PentahoLoteResposta, status_code=status.HTTP_202_ACCEPTED)
def receber_lote(
    payload: PentahoLoteEntrada,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(..., alias='Idempotency-Key', min_length=1, max_length=128),
    correlation_id: str = Header(..., alias='X-Correlation-Id', min_length=1, max_length=128),
    db: Session = Depends(get_db),
    _auth: ServiceAuthContext = Depends(_autorizar_pentaho),
):
    lote, duplicado = criar_ou_obter_lote(db, payload, idempotency_key, correlation_id)
    if not duplicado:
        background_tasks.add_task(processar_lote_assincrono, lote.lote_id)

    return PentahoLoteResposta(
        loteId=lote.lote_id,
        correlationId=lote.correlation_id,
        status=lote.status,
        duplicado=duplicado,
        consulta=f'/api/integracoes/pentaho/lotes/{lote.lote_id}',
    )


@router.get('/lotes/{lote_id}', response_model=PentahoLoteStatus)
def consultar_lote(
    lote_id: str,
    db: Session = Depends(get_db),
    _auth: ServiceAuthContext = Depends(_autorizar_pentaho),
):
    return PentahoLoteStatus(**serializar_status(obter_lote(db, lote_id)))


@router.post('/lotes/{lote_id}/reprocessar', response_model=PentahoLoteResposta, status_code=status.HTTP_202_ACCEPTED)
def reprocessar_lote(
    lote_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _auth: ServiceAuthContext = Depends(_autorizar_pentaho),
):
    lote = preparar_reprocessamento(db, lote_id)
    background_tasks.add_task(processar_lote_assincrono, lote.lote_id)
    return PentahoLoteResposta(
        loteId=lote.lote_id,
        correlationId=lote.correlation_id,
        status=lote.status,
        duplicado=False,
        consulta=f'/api/integracoes/pentaho/lotes/{lote.lote_id}',
    )


@router.get('/dashboard')
def dashboard_pentaho(
    limite: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _auth: ServiceAuthContext = Depends(_autorizar_pentaho),
):
    return obter_dashboard(db, limite=limite)
