from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.envelope import ok
from app.db import get_db
from app.services.rag_governado import (
    ENGINE_MEMORIA,
    carregar_documentos_do_diretorio,
    indexar_chunks_persistentes,
    normalizar_documentos,
    responder_rag_governado,
    responder_rag_governado_persistido,
)

router = APIRouter(prefix='/api/rag', tags=['rag-governado'])


class DocumentoRAGRequest(BaseModel):
    id: str | None = None
    titulo: str | None = None
    conteudo: str = Field(..., min_length=3, max_length=20000)
    origem: str | None = None


class PerguntaRAGRequest(BaseModel):
    pergunta: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=8)
    documentos: list[DocumentoRAGRequest] = Field(default_factory=list)


class IndexarRAGRequest(BaseModel):
    documentos: list[DocumentoRAGRequest] = Field(..., min_length=1)


def _resultado_para_payload(resultado) -> dict:
    return {
        'resposta': resultado.resposta,
        'fontes': [fonte.__dict__ for fonte in resultado.fontes],
        'statusFluxo': resultado.status_fluxo,
        'engine': resultado.engine,
        'avisos': resultado.avisos,
        'mascaramentoAplicado': resultado.mascaramento_aplicado,
        'evidenciaObrigatoria': True,
    }


@router.post('/perguntas')
def perguntar_rag_governado(payload: PerguntaRAGRequest, db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    documentos_payload = normalizar_documentos([item.model_dump() for item in payload.documentos])
    documentos_configurados = carregar_documentos_do_diretorio(getattr(settings, 'reqsys_rag_documents_path', ''))
    documentos = documentos_payload or documentos_configurados

    if documentos:
        resultado = responder_rag_governado(
            payload.pergunta,
            documentos,
            top_k=payload.top_k,
            correlation_id=x_correlation_id,
        )
    else:
        resultado = responder_rag_governado_persistido(
            db,
            payload.pergunta,
            top_k=payload.top_k,
            correlation_id=x_correlation_id,
        )

    return ok(
        _resultado_para_payload(resultado),
        correlation_id=resultado.correlation_id,
        meta={'fontes_recuperadas': len(resultado.fontes)},
    )


@router.post('/indexar')
def indexar_rag_governado(payload: IndexarRAGRequest, db: Session = Depends(get_db), x_correlation_id: str | None = Header(default=None)):
    documentos = normalizar_documentos([item.model_dump() for item in payload.documentos])
    total = indexar_chunks_persistentes(db, documentos)
    return ok(
        {'documentosRecebidos': len(payload.documentos), 'chunksIndexados': total},
        correlation_id=x_correlation_id,
    )


@router.get('/health')
def rag_health():
    return ok(
        {
            'service': 'rag-governado',
            'status': 'ok',
            'motorSemantico': ENGINE_MEMORIA,
            'documentsPathConfigured': bool(getattr(settings, 'reqsys_rag_documents_path', '')),
            'modo': 'governado-com-fontes-obrigatorias',
        }
    )
