from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.services.ai_quality import (
    calcular_resumo_qualidade_ia,
    exportar_tendencia_csv,
    exportar_tendencia_pdf,
    listar_tendencia,
    registrar_snapshot_qualidade_ia,
)

router = APIRouter(prefix='/v1/qualidade-ia', tags=['Qualidade IA'])


@router.get('/resumo')
def resumo(db: Session = Depends(get_db)):
    payload = calcular_resumo_qualidade_ia(db)
    payload['tendencia'] = listar_tendencia(db, limit=20)
    return ok(payload)


@router.post('/snapshot')
def snapshot(db: Session = Depends(get_db)):
    payload = registrar_snapshot_qualidade_ia(db)
    return ok(payload)


@router.get('/tendencia')
def tendencia(limit: int = 20, dias: Optional[int] = None, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    if dias is not None:
        dias = max(1, min(dias, 365))
    return ok({'itens': listar_tendencia(db, limit=limit, dias=dias), 'limit': limit, 'dias': dias})


@router.get('/tendencia.csv')
def tendencia_csv(limit: int = 200, dias: Optional[int] = None, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 1000))
    if dias is not None:
        dias = max(1, min(dias, 365))
    csv_content = exportar_tendencia_csv(listar_tendencia(db, limit=limit, dias=dias))
    nome = f'qualidade-ia-tendencia{f"-{dias}d" if dias else ""}.csv'
    return Response(
        content=csv_content,
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{nome}"'},
    )


@router.get('/tendencia.pdf')
def tendencia_pdf(limit: int = 200, dias: Optional[int] = None, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 1000))
    if dias is not None:
        dias = max(1, min(dias, 365))
    pdf_content = exportar_tendencia_pdf(listar_tendencia(db, limit=limit, dias=dias))
    nome = f'qualidade-ia-tendencia{f"-{dias}d" if dias else ""}.pdf'
    return Response(
        content=pdf_content,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{nome}"'},
    )
