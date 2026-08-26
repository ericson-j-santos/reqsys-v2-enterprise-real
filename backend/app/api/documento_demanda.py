from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.db import get_db
from app.models.documento_demanda import DocumentoDemandaAnalise
from app.ocr.documento_worker import (
    EVENTO_OCR_DOCUMENTO_DEMANDA_SOLICITADO,
    DocumentoDemandaOcrWorker,
    RepositorioOcrDocumentoMemoria,
    TesseractDocumento,
    ocr_documento_readiness,
    registrar_documento_demanda_ocr_worker,
)
from app.services.documento_demanda import (
    TIPOS_OCR_DOCUMENTO,
    calcular_sha256,
    classificar_candidatos,
    classificar_candidatos_por_paginas,
    extrair_texto_basico,
    serializar_candidatos,
    validar_upload,
)
from app.services.runtime_core import RuntimeEventBus, RuntimeEventEnvelope, RuntimeEventStatus

router = APIRouter(prefix='/demandas/documentos', tags=['Documentos da demanda'])
_TRUE_VALUES = {'1', 'true', 'yes', 'on'}
_EXTENSAO_POR_TIPO = {
    'application/pdf': '.pdf',
    'image/png': '.png',
    'image/jpeg': '.jpg',
}


def _ocr_documento_habilitado() -> bool:
    flag = (os.getenv('DOCUMENTO_DEMANDA_OCR_ENABLED') or '').strip().lower() in _TRUE_VALUES
    ambiente_permitido = settings.normalized_environment in {'desenvolvimento', 'testes'}
    return flag and ambiente_permitido


def _novo_motor_ocr_documento() -> TesseractDocumento:
    return TesseractDocumento(
        idioma=(os.getenv('DOCUMENTO_DEMANDA_OCR_LANG') or 'por').strip() or 'por',
        dpi_pdf=int(os.getenv('DOCUMENTO_DEMANDA_OCR_DPI') or '200'),
        timeout_segundos=float(os.getenv('DOCUMENTO_DEMANDA_OCR_TIMEOUT_SECONDS') or '60'),
        max_paginas=int(os.getenv('DOCUMENTO_DEMANDA_OCR_MAX_PAGES') or '25'),
    )


def _payload_registro(registro: DocumentoDemandaAnalise, *, idempotente: bool) -> dict[str, object]:
    return {
        'id': registro.id,
        'demanda_ref': registro.demanda_ref,
        'sha256': registro.sha256,
        'status': registro.status,
        'candidatos': json.loads(registro.candidatos_json or '[]'),
        'idempotente': idempotente,
        'incorporacao_automatica': False,
    }


def _processar_ocr_documento(
    registro: DocumentoDemandaAnalise,
    conteudo: bytes,
    db: Session,
) -> None:
    registro.status = 'PROCESSANDO_OCR'
    registro.erro = ''
    db.commit()
    db.refresh(registro)

    diretorio = Path(tempfile.mkdtemp(prefix='reqsys_demanda_ocr_'))
    try:
        try:
            diretorio.chmod(0o700)
        except OSError:
            pass
        extensao = _EXTENSAO_POR_TIPO[registro.content_type]
        nome_seguro = f'{registro.sha256}{extensao}'
        entrada = diretorio / nome_seguro
        entrada.write_bytes(conteudo)
        try:
            entrada.chmod(0o600)
        except OSError:
            pass

        repositorio = RepositorioOcrDocumentoMemoria()
        worker = DocumentoDemandaOcrWorker(
            _novo_motor_ocr_documento(),
            repositorio,
            input_root=diretorio,
        )
        bus = RuntimeEventBus()
        registrar_documento_demanda_ocr_worker(bus, worker)
        envelope = RuntimeEventEnvelope(
            event_type=EVENTO_OCR_DOCUMENTO_DEMANDA_SOLICITADO,
            source='api.documento_demanda',
            aggregate_type='documento_demanda_ocr',
            aggregate_id=str(registro.id),
            correlation_id=registro.correlation_id,
            payload={
                'document_ref': nome_seguro,
                'content_type': registro.content_type,
            },
        )
        entrega = bus.publish(envelope)[0]
        if entrega.status is not RuntimeEventStatus.DELIVERED:
            registro.status = 'ERRO_OCR'
            registro.erro = f'OCR_PROCESSING_FAILED:{entrega.status.value}'
            db.commit()
            raise HTTPException(
                status_code=503,
                detail={
                    'code': 'OCR_PROCESSING_FAILED',
                    'status': entrega.status.value,
                    'attempts': entrega.attempts,
                    'correlation_id': registro.correlation_id,
                },
            )

        resultado = repositorio.obter(str(registro.id))
        if resultado is None:
            registro.status = 'ERRO_OCR'
            registro.erro = 'OCR_RESULT_NOT_FOUND'
            db.commit()
            raise HTTPException(status_code=503, detail='OCR_RESULT_NOT_FOUND')

        candidatos = classificar_candidatos_por_paginas(
            [(pagina.pagina, pagina.texto, pagina.confianca) for pagina in resultado.paginas]
        )
        registro.texto_extraido = resultado.texto
        registro.candidatos_json = serializar_candidatos(candidatos)
        registro.status = 'AGUARDANDO_REVISAO_HUMANA'
        registro.erro = ''
        db.commit()
        db.refresh(registro)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        registro.status = 'ERRO_OCR'
        registro.erro = f'OCR_PROCESSING_FAILED:{type(exc).__name__}'
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={
                'code': 'OCR_PROCESSING_FAILED',
                'correlation_id': registro.correlation_id,
            },
        ) from None
    finally:
        shutil.rmtree(diretorio, ignore_errors=True)


@router.get('/ocr-readiness')
def obter_prontidao_ocr_documento(user: dict = Depends(require_admin)):
    del user
    return ok(
        {
            'enabled': _ocr_documento_habilitado(),
            'environment': settings.normalized_environment,
            **ocr_documento_readiness(),
        }
    )


@router.post('/analisar')
async def analisar_documento_demanda(
    demanda_ref: str = Form(min_length=1, max_length=120),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-Id'),
):
    del user
    correlation_id = resolver_correlation_id(x_correlation_id, str(uuid4()))
    conteudo = await arquivo.read()
    content_type = arquivo.content_type or 'application/octet-stream'
    try:
        validar_upload(nome_arquivo=arquivo.filename or '', content_type=content_type, conteudo=conteudo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    sha256 = calcular_sha256(conteudo)
    demanda_ref = demanda_ref.strip()
    existente = db.query(DocumentoDemandaAnalise).filter(
        DocumentoDemandaAnalise.demanda_ref == demanda_ref,
        DocumentoDemandaAnalise.sha256 == sha256,
    ).first()
    if existente:
        if (
            _ocr_documento_habilitado()
            and content_type in TIPOS_OCR_DOCUMENTO
            and existente.status in {'AGUARDANDO_OCR', 'ERRO_OCR'}
        ):
            _processar_ocr_documento(existente, conteudo, db)
        return ok(_payload_registro(existente, idempotente=True), existente.correlation_id)

    texto = extrair_texto_basico(content_type, conteudo)
    status = 'AGUARDANDO_OCR' if not texto else 'AGUARDANDO_REVISAO_HUMANA'
    candidatos = classificar_candidatos(texto) if texto else []
    registro = DocumentoDemandaAnalise(
        demanda_ref=demanda_ref,
        nome_arquivo=arquivo.filename or 'arquivo',
        content_type=content_type,
        sha256=sha256,
        correlation_id=correlation_id,
        status=status,
        texto_extraido=texto,
        candidatos_json=serializar_candidatos(candidatos),
    )
    db.add(registro)
    try:
        db.commit()
        db.refresh(registro)
    except IntegrityError:
        db.rollback()
        existente = db.query(DocumentoDemandaAnalise).filter(
            DocumentoDemandaAnalise.demanda_ref == demanda_ref,
            DocumentoDemandaAnalise.sha256 == sha256,
        ).first()
        if existente:
            if (
                _ocr_documento_habilitado()
                and content_type in TIPOS_OCR_DOCUMENTO
                and existente.status in {'AGUARDANDO_OCR', 'ERRO_OCR'}
            ):
                _processar_ocr_documento(existente, conteudo, db)
            return ok(_payload_registro(existente, idempotente=True), existente.correlation_id)
        raise

    if _ocr_documento_habilitado() and content_type in TIPOS_OCR_DOCUMENTO:
        _processar_ocr_documento(registro, conteudo, db)

    return ok(_payload_registro(registro, idempotente=False), correlation_id)


@router.get('/{analise_id}')
def obter_analise_documento(
    analise_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    del user
    registro = db.get(DocumentoDemandaAnalise, analise_id)
    if registro is None:
        raise HTTPException(status_code=404, detail='Análise documental não encontrada')
    return ok(
        {
            'id': registro.id,
            'demanda_ref': registro.demanda_ref,
            'nome_arquivo': registro.nome_arquivo,
            'content_type': registro.content_type,
            'sha256': registro.sha256,
            'status': registro.status,
            'candidatos': json.loads(registro.candidatos_json or '[]'),
            'incorporacao_automatica': False,
        },
        registro.correlation_id,
    )
