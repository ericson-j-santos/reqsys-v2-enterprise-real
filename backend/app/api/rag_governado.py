from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.envelope import ok
from app.services.rag_governado import (
    carregar_documentos_do_diretorio,
    llama_index_disponivel,
    normalizar_documentos,
    responder_rag_governado,
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


@router.post('/perguntas')
def perguntar_rag_governado(payload: PerguntaRAGRequest, x_correlation_id: str | None = Header(default=None)):
    documentos_payload = normalizar_documentos([item.model_dump() for item in payload.documentos])
    documentos_configurados = carregar_documentos_do_diretorio(getattr(settings, 'reqsys_rag_documents_path', ''))
    documentos = documentos_payload or documentos_configurados

    resultado = responder_rag_governado(
        payload.pergunta,
        documentos,
        top_k=payload.top_k,
        correlation_id=x_correlation_id,
    )

    return ok(
        {
            'resposta': resultado.resposta,
            'fontes': [fonte.__dict__ for fonte in resultado.fontes],
            'statusFluxo': resultado.status_fluxo,
            'engine': resultado.engine,
            'avisos': resultado.avisos,
            'mascaramentoAplicado': resultado.mascaramento_aplicado,
            'evidenciaObrigatoria': True,
        },
        correlation_id=resultado.correlation_id,
        meta={'fontes_recuperadas': len(resultado.fontes)},
    )


@router.get('/health')
def rag_health():
    return ok(
        {
            'service': 'rag-governado',
            'status': 'ok',
            'llamaIndexDisponivel': llama_index_disponivel(),
            'documentsPathConfigured': bool(getattr(settings, 'reqsys_rag_documents_path', '')),
            'modo': 'governado-com-fontes-obrigatorias',
        }
    )
