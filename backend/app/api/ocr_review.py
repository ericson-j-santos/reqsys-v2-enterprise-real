"""API governada do bounded context OCR.

Somente administradores autenticados podem processar documentos, revelar o
resultado protegido e decidir itens pendentes de revisão humana.
"""
from __future__ import annotations

import hashlib
import os
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.documento_demanda import router as documento_demanda_router
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.ocr.redmine import (
    RedmineAttachmentClient,
    RedmineAttachmentError,
    RedmineAttachmentUnsupported,
)
from app.ocr.storage import (
    RepositorioClaimsOcrSqlAlchemy,
    RepositorioResultadosOcrSqlAlchemy,
    ocr_store_readiness,
)
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


class OcrRedmineAttachmentsRequest(BaseModel):
    campo: Literal['nome'] = 'nome'
    limite: int = Field(default=20, ge=1, le=100)


class OcrDecisionRequest(BaseModel):
    decisao: Literal['APROVADO', 'REJEITADO']
    observacao: str = Field(default='', max_length=1000)


def _repo() -> RepositorioResultadosOcrSqlAlchemy:
    try:
        return RepositorioResultadosOcrSqlAlchemy()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f'OCR_STORE_NOT_READY: {exc}') from None


def _claims() -> RepositorioClaimsOcrSqlAlchemy:
    try:
        return RepositorioClaimsOcrSqlAlchemy()
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f'OCR_CLAIM_STORE_NOT_READY: {exc}') from None


def _owner_token(correlation_id: str) -> str:
    correlation_hash = hashlib.sha256(correlation_id.encode('utf-8')).hexdigest()[:32]
    return f'{correlation_hash}:{uuid4()}'


def _reviewer_id(user: dict) -> str:
    return str(user.get('sub') or user.get('email') or user.get('preferred_username') or 'admin-sem-identificador')


def _runtime_ocr(repo: RepositorioResultadosOcrSqlAlchemy, input_root: str) -> RuntimeEventBus:
    bus = RuntimeEventBus()
    registrar_ocr_worker(bus, OcrWorker(MotorOcrEvidencia(), repo, input_root=input_root))
    return bus


@router.get('/readiness')
def readiness_ocr():
    store = ocr_store_readiness()
    input_root = (os.getenv('OCR_INPUT_ROOT') or '').strip()
    return {**store, 'input_root_configured': bool(input_root), 'engine': 'tesseract-multipass', 'engine_language': 'por', 'ready': bool(store['ready'] and input_root)}


@router.post('/jobs')
def criar_job_ocr(payload: OcrJobRequest, user: dict = Depends(require_admin), x_correlation_id: str | None = Header(default=None, alias='X-Correlation-Id')):
    del user
    input_root = (os.getenv('OCR_INPUT_ROOT') or '').strip()
    if not input_root:
        raise HTTPException(status_code=503, detail='OCR_INPUT_ROOT não configurado')
    job_id = f'ocr-{uuid4()}'
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    repo = _repo()
    bus = _runtime_ocr(repo, input_root)
    envelope = RuntimeEventEnvelope(event_type=EVENTO_OCR_SOLICITADO, source='api.ocr', aggregate_type='ocr_job', aggregate_id=job_id, correlation_id=correlation_id, payload={'document_ref': payload.document_ref, 'tipo_documento': payload.tipo_documento, 'campo': payload.campo, 'recorte': list(payload.recorte) if payload.recorte else None})
    entrega = bus.publish(envelope)[0]
    if entrega.status is not RuntimeEventStatus.DELIVERED:
        raise HTTPException(status_code=422 if entrega.status is RuntimeEventStatus.DEAD_LETTER else 503, detail={'code': 'OCR_PROCESSING_FAILED', 'job_id': job_id, 'correlation_id': correlation_id, 'status': entrega.status.value, 'attempts': entrega.attempts, 'error': entrega.error})
    resultado = repo.obter(job_id, revelar_pii=False)
    return ok(resultado, correlation_id)


@router.post('/redmine/issues/{issue_id}/attachments')
def processar_anexos_redmine(issue_id: int, payload: OcrRedmineAttachmentsRequest, user: dict = Depends(require_admin), x_correlation_id: str | None = Header(default=None, alias='X-Correlation-Id')):
    """Materializa anexos Redmine e garante uma única execução OCR ativa por job_id."""
    del user
    input_root = (os.getenv('OCR_INPUT_ROOT') or '').strip()
    if not input_root:
        raise HTTPException(status_code=503, detail='OCR_INPUT_ROOT não configurado')

    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        client = RedmineAttachmentClient()
        attachments = client.list_attachments(issue_id)
    except RedmineAttachmentError as exc:
        raise HTTPException(status_code=502, detail={'code': 'OCR_REDMINE_SOURCE_UNAVAILABLE', 'correlation_id': correlation_id, 'error': str(exc)}) from None

    repo = _repo()
    claims = _claims()
    bus: RuntimeEventBus | None = None
    items: list[dict[str, object]] = []
    failed_count = 0
    processed_count = 0
    already_processed_count = 0
    in_progress_count = 0
    unsupported_count = 0

    for attachment in attachments[: payload.limite]:
        try:
            imported = client.import_attachment(issue_id, attachment, input_root=input_root)
        except RedmineAttachmentUnsupported as exc:
            unsupported_count += 1
            items.append({'attachment_id': attachment.attachment_id, 'status': 'IGNORADO_FORMATO', 'reason': str(exc)})
            continue
        except RedmineAttachmentError as exc:
            failed_count += 1
            items.append({'attachment_id': attachment.attachment_id, 'status': 'QUARENTENA', 'reason': str(exc)})
            continue

        job_id = f'ocr-redmine-{issue_id}-{imported.attachment_id}-{imported.sha256[:16]}'
        existing = repo.obter(job_id, revelar_pii=False)
        if existing is not None:
            already_processed_count += 1
            items.append({'attachment_id': imported.attachment_id, 'status': 'JA_PROCESSADO', 'job_id': job_id, 'sha256': imported.sha256, 'resultado': existing})
            continue

        owner_token = _owner_token(correlation_id)
        if not claims.adquirir(job_id, owner_token):
            existing = repo.obter(job_id, revelar_pii=False)
            if existing is not None:
                already_processed_count += 1
                items.append({'attachment_id': imported.attachment_id, 'status': 'JA_PROCESSADO', 'job_id': job_id, 'sha256': imported.sha256, 'resultado': existing})
            else:
                in_progress_count += 1
                items.append({'attachment_id': imported.attachment_id, 'status': 'EM_PROCESSAMENTO', 'job_id': job_id, 'sha256': imported.sha256})
            continue

        try:
            existing = repo.obter(job_id, revelar_pii=False)
            if existing is not None:
                already_processed_count += 1
                items.append({'attachment_id': imported.attachment_id, 'status': 'JA_PROCESSADO', 'job_id': job_id, 'sha256': imported.sha256, 'resultado': existing})
                continue

            if bus is None:
                bus = _runtime_ocr(repo, input_root)
            envelope = RuntimeEventEnvelope(
                event_type=EVENTO_OCR_SOLICITADO,
                source='redmine.attachment',
                aggregate_type='ocr_job',
                aggregate_id=job_id,
                correlation_id=correlation_id,
                causation_id=f'redmine-issue-{issue_id}-attachment-{imported.attachment_id}',
                payload={'document_ref': imported.document_ref, 'tipo_documento': imported.tipo_documento, 'campo': payload.campo, 'redmine_issue_id': issue_id, 'redmine_attachment_id': imported.attachment_id, 'sha256': imported.sha256},
            )
            entrega = bus.publish(envelope)[0]
            if entrega.status is not RuntimeEventStatus.DELIVERED:
                failed_count += 1
                items.append({'attachment_id': imported.attachment_id, 'status': 'FALHA_OCR', 'job_id': job_id, 'sha256': imported.sha256, 'runtime_status': entrega.status.value, 'attempts': entrega.attempts, 'reason': entrega.error})
                continue

            resultado = repo.obter(job_id, revelar_pii=False)
            if resultado is None:
                failed_count += 1
                items.append({'attachment_id': imported.attachment_id, 'status': 'FALHA_PERSISTENCIA', 'job_id': job_id, 'sha256': imported.sha256})
                continue
            processed_count += 1
            items.append({'attachment_id': imported.attachment_id, 'status': 'PROCESSADO', 'job_id': job_id, 'sha256': imported.sha256, 'resultado': resultado})
        finally:
            claims.liberar(job_id, owner_token)

    data = {
        'redmine_issue_id': issue_id,
        'attachments_found': len(attachments),
        'attachments_considered': min(len(attachments), payload.limite),
        'processed_count': processed_count,
        'already_processed_count': already_processed_count,
        'in_progress_count': in_progress_count,
        'unsupported_count': unsupported_count,
        'failed_count': failed_count,
        'items': items,
        'pii_exposta': False,
        'fail_closed': True,
        'distributed_claim': True,
    }
    if failed_count:
        raise HTTPException(status_code=422, detail={'code': 'OCR_REDMINE_ATTACHMENTS_PARTIAL_FAILURE', 'correlation_id': correlation_id, 'data': data})
    return ok(data, correlation_id)


@router.get('/review')
def listar_revisao_ocr(status: str | None = 'PENDENTE', limite: int = 100, user: dict = Depends(require_admin)):
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
def decidir_revisao_ocr(job_id: str, payload: OcrDecisionRequest, user: dict = Depends(require_admin)):
    try:
        item = _repo().decidir(job_id, decisao=payload.decisao, reviewer=_reviewer_id(user), observacao=payload.observacao)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return ok(item)
