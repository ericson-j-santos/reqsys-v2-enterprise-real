from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.correlation import obter_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.db import get_db
from app.services.auditoria import registrar_evento
from app.services.cdi_provider import (
    CdiProviderError,
    atualizar_cdi_do_bcb,
    obter_cdi_atual,
)

router = APIRouter(prefix='/v1/financeiro', tags=['Financeiro'])


@router.get('/cdi/latest')
def cdi_latest(db: Session = Depends(get_db)):
    taxa = obter_cdi_atual(db)
    if taxa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Taxa CDI ainda nao foi carregada no cache interno.',
        )
    return ok(taxa)


@router.post('/cdi/refresh')
def cdi_refresh(db: Session = Depends(get_db), admin: dict = Depends(require_admin)):
    correlation_id = obter_correlation_id()
    usuario = admin.get('sub') or 'desconhecido'
    try:
        resultado = atualizar_cdi_do_bcb(db)
        registrar_evento(db, correlation_id, usuario, 'CDI_REFRESH_SUCESSO', 'cdi_rate', resultado['reference_date'])
        return ok(resultado)
    except CdiProviderError as exc:
        cached = obter_cdi_atual(db)
        registrar_evento(
            db,
            correlation_id,
            usuario,
            'CDI_REFRESH_FALHA',
            'cdi_rate',
            cached['reference_date'] if cached else 'sem-cache',
        )
        if cached is not None:
            cached['stale'] = True
            return ok(
                cached,
                meta={
                    'warning': 'Falha ao atualizar CDI no Banco Central; retornando ultimo valor interno.',
                    'detail': str(exc),
                },
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
