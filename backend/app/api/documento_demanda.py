from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.db import get_db
from app.models.documento_demanda import DocumentoDemandaAnalise
from app.services.documento_demanda import (
    calcular_sha256,
    classificar_candidatos,
    extrair_texto_basico,
    serializar_candidatos,
    validar_upload,
)

router = APIRouter(prefix='/v1/demandas/documentos', tags=['Documentos da demanda'])


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
    existente = (
        db.query(DocumentoDemandaAnalise)
        .filter(
            DocumentoDemandaAnalise.demanda_ref == demanda_ref,
            DocumentoDemandaAnalise.sha256 == sha256,
        )
        .first()
    )
    if existente:
        return ok(
            {
                'id': existente.id,
                'demanda_ref': existente.demanda_ref,
                'sha256': existente.sha256,
                'status': existente.status,
                'candidatos': json.loads(existente.candidatos_json or '[]'),
                'idempotente': True,
            },
            existente.correlation_id,
        )

    texto = extrair_texto_basico(content_type, conteudo)
    status = 'AGUARDANDO_OCR' if not texto else 'AGUARDANDO_REVISAO_HUMANA'
    candidatos = classificar_candidatos(texto) if texto else []

    registro = DocumentoDemandaAnalise(
        demanda_ref=demanda_ref.strip(),
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
        existente = (
            db.query(DocumentoDemandaAnalise)
            .filter(
                DocumentoDemandaAnalise.demanda_ref == demanda_ref,
                DocumentoDemandaAnalise.sha256 == sha256,
            )
            .first()
        )
        if existente:
            return ok(
                {
                    'id': existente.id,
                    'demanda_ref': existente.demanda_ref,
                    'sha256': existente.sha256,
                    'status': existente.status,
                    'candidatos': json.loads(existente.candidatos_json or '[]'),
                    'idempotente': True,
                },
                existente.correlation_id,
            )
        raise

    return ok(
        {
            'id': registro.id,
            'demanda_ref': registro.demanda_ref,
            'sha256': registro.sha256,
            'status': registro.status,
            'candidatos': [c.__dict__ for c in candidatos],
            'idempotente': False,
            'incorporacao_automatica': False,
        },
        correlation_id,
    )


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
