"""API governada do bounded context OCR.

Somente administradores autenticados podem processar documentos, revelar o
resultado protegido e decidir itens pendentes de revisão humana.
"""
from __future__ import annotations

import os
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.documento_demanda import router as documento_demanda_router
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.ocr.storage import RepositorioResultadosOcrSqlAlchemy, ocr_store_readiness
from app.ocr.worker import (
    EVENTO_OCR_SOLICITADO,
    MotorOcrEvidencia,
    OcrWorker,
    registrar_ocr_worker,
)
from app.services.runtime_core import (
    RuntimeEventBus,
    RuntimeEventEnvelope,
    RuntimeEventStatus,
)

router = APIRouter(prefix='/v1/ocr', tags=['OCR Governado'])
router.include_router(documento_demanda_router)


class OcrJobRequest(BaseModel):
    document_ref: str = Field(min_length=1, max_length=500)
    tipo_documento: str = Field(default='DESCONHECIDO', min_length=1, max_length=80)
    campo: Literal['nome'] = 'nome'
    recorte: tuple[int, int, int, int] | None = None


class OcrDecisionRequest(BaseModel):
    decisao: Literal['APROVADO', 'REJEITADO']
    observacao: str = Field(default='', max_length=1000)


def _repo() -> RepositorioResultadosOcrSqlAlchemy:
    try:
        return RepositorioResultadosOcrSqlAlchemy()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f'OCR_STORE_NOT_READY: {exc}') from None


def _reviewer_id(user: dict) -> str:
    return str(user.get('sub') or user.get('email') or user.get('preferred_username') or 'admin-sem-identificador')


@router.get('/readiness', dependencies=[Depends(require_admin)])
def readiness_ocr():
    store = ocr_store_readiness()
    input_root = (os.getenv('OCR_INPUT_ROOT') or '').strip()
    payload = {
        **store,
        'input_root_configured': bool(input_root),
        'engine': 'tesseract-multipass',
        'engine_language': 'por',
        'ready': bool(store['ready'] and input_root),
    }
    return ok(payload)


@router.post('/jobs')
def criar_job_ocr(
    payload: OcrJobRequest,
    user: dict = Depends(require_admin),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-Id'),
):
    del user  # autorização já validada; identidade não entra no payload OCR.
    input_root = (os.getenv('OCR_INPUT_ROOT') or '').strip()
    if not input_root:
        raise HTTPException(status_code=503, detail='OCR_INPUT_ROOT não configurado')

    job_id = f'ocr-{uuid4()}'
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    repo = _repo()
    worker = OcrWorker(MotorOcrEvidencia(), repo, input_root=input_root)
    bus = RuntimeEventBus()
    registrar_ocr_worker(bus, worker)
    envelope = RuntimeEventEnvelope(
        event_type=EVENTO_OCR_SOLICITADO,
        source='api.ocr',
        aggregate_type='ocr_job',
        aggregate_id=job_id,
        correlation_id=correlation_id,
        payload={
            'document_ref': payload.document_ref,
            'tipo_documento': payload.tipo_documento,
            'campo': payload.campo,
            'recorte': list(payload.recorte) if payload.recorte else None,
        },
    )
    entrega = bus.publish(envelope)[0]
    if entrega.status is not RuntimeEventStatus.DELIVERED:
        raise HTTPException(
            status_code=422 if entrega.status is RuntimeEventStatus.DEAD_LETTER else 503,
            detail={
                'code': 'OCR_PROCESSING_FAILED',
                'job_id': job_id,
                'correlation_id': correlation_id,
                'status': entrega.status.value,
                'attempts': entrega.attempts,
                'error': entrega.error,
            },
        )
    resultado = repo.obter(job_id, revelar_pii=False)
    return ok(resultado, correlation_id)


@router.get('/review')
def listar_revisao_ocr(
    status: str | None = 'PENDENTE',
    limite: int = 100,
    user: dict = Depends(require_admin),
):
    del user
    itens = _repo().listar(status=status, limite=limite)
    return ok({'items': itens, 'count': len(itens), 'pii_exposta': False})


@router.get('/review/{job_id}')
def detalhar_revisao_ocr(job_id: str, user: dict = Depends(require_admin)):
    del user
    item = _repo().obter(job_id, revelar_pii=True)
    if item is None:
        raise HTTPException(status_code=404, detail='Resultado OCR não encontrado')
    item['pii_exposta'] = True
    item['exposicao'] = 'somente resposta autenticada; não registrar em logs/artifacts'
    return ok(item)


@router.post('/review/{job_id}/decision')
def decidir_revisao_ocr(
    job_id: str,
    payload: OcrDecisionRequest,
    user: dict = Depends(require_admin),
):
    try:
        item = _repo().decidir(
            job_id,
            decisao=payload.decisao,
            reviewer=_reviewer_id(user),
            observacao=payload.observacao,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return ok(item)
