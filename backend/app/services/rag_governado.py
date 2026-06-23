from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger('reqsys.rag')

PII_PATTERNS = (
    re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'),
    re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
)


@dataclass(frozen=True)
class DocumentoRAG:
    id: str
    titulo: str
    conteudo: str
    origem: str = 'payload'


@dataclass(frozen=True)
class FonteRAG:
    id: str
    titulo: str
    origem: str
    score: float
    trecho: str


@dataclass(frozen=True)
class RespostaRAG:
    resposta: str
    fontes: list[FonteRAG]
    correlation_id: str
    status_fluxo: str
    engine: str
    avisos: list[str]
    mascaramento_aplicado: bool = True


def gerar_correlation_id(prefixo: str = 'rag') -> str:
    return f'{prefixo}-{uuid4()}'


def mascarar_pii(texto: str) -> str:
    texto_mascarado = texto
    for pattern in PII_PATTERNS:
        texto_mascarado = pattern.sub('[DADO_MASCARADO]', texto_mascarado)
    return texto_mascarado


def normalizar_documentos(documentos: list[dict[str, Any]] | None) -> list[DocumentoRAG]:
    normalizados: list[DocumentoRAG] = []
    for index, item in enumerate(documentos or [], start=1):
        conteudo = str(item.get('conteudo') or item.get('content') or '').strip()
        if not conteudo:
            continue
        normalizados.append(
            DocumentoRAG(
                id=str(item.get('id') or f'doc-{index}'),
                titulo=str(item.get('titulo') or item.get('title') or f'Documento {index}'),
                conteudo=mascarar_pii(conteudo),
                origem=str(item.get('origem') or item.get('source') or 'payload'),
            )
        )
    return normalizados


def carregar_documentos_do_diretorio(caminho: str | None) -> list[DocumentoRAG]:
    if not caminho:
        return []
    raiz = Path(caminho).expanduser().resolve()
    if not raiz.exists() or not raiz.is_dir():
        logger.warning('rag_documents_path_invalido path=%s', raiz)
        return []

    documentos: list[DocumentoRAG] = []
    for arquivo in sorted(raiz.glob('**/*.md')) + sorted(raiz.glob('**/*.txt')):
        if arquivo.is_file():
            conteudo = mascarar_pii(arquivo.read_text(encoding='utf-8', errors='ignore'))
            documentos.append(
                DocumentoRAG(
                    id=arquivo.stem,
                    titulo=arquivo.name,
                    conteudo=conteudo,
                    origem=str(arquivo.relative_to(raiz)),
                )
            )
    return documentos


def _termos(texto: str) -> set[str]:
    return {termo for termo in re.findall(r'[a-zA-ZÀ-ÿ0-9_]{3,}', texto.lower())}


def _trecho_relevante(conteudo: str, termos_pergunta: set[str], limite: int = 520) -> str:
    paragrafos = [p.strip() for p in re.split(r'\n\s*\n', conteudo) if p.strip()]
    if not paragrafos:
        return conteudo[:limite]

    melhor = max(
        paragrafos,
        key=lambda p: len(_termos(p) & termos_pergunta),
    )
    return melhor[:limite]


def recuperar_fontes_lexical(pergunta: str, documentos: list[DocumentoRAG], top_k: int = 4) -> list[FonteRAG]:
    termos_pergunta = _termos(pergunta)
    if not termos_pergunta:
        return []

    ranqueados: list[FonteRAG] = []
    for documento in documentos:
        termos_documento = _termos(documento.conteudo + ' ' + documento.titulo)
        intersecao = termos_pergunta & termos_documento
        if not intersecao:
            continue
        score = len(intersecao) / max(len(termos_pergunta), 1)
        ranqueados.append(
            FonteRAG(
                id=documento.id,
                titulo=documento.titulo,
                origem=documento.origem,
                score=round(score, 4),
                trecho=_trecho_relevante(documento.conteudo, termos_pergunta),
            )
        )

    return sorted(ranqueados, key=lambda fonte: fonte.score, reverse=True)[:top_k]


def llama_index_disponivel() -> bool:
    try:
        import llama_index.core  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 - dependencia opcional e governada
        return False


def responder_rag_governado(
    pergunta: str,
    documentos: list[DocumentoRAG],
    *,
    top_k: int = 4,
    correlation_id: str | None = None,
) -> RespostaRAG:
    correlation_id = correlation_id or gerar_correlation_id()
    pergunta_mascarada = mascarar_pii(pergunta.strip())

    fontes = recuperar_fontes_lexical(pergunta_mascarada, documentos, top_k=top_k)
    engine = 'llama-index-ready+lexical-fallback' if llama_index_disponivel() else 'lexical-fallback'

    if not fontes:
        logger.info('rag_sem_evidencia correlation_id=%s engine=%s', correlation_id, engine)
        return RespostaRAG(
            resposta='Não há evidência suficiente nas fontes disponíveis para responder com segurança.',
            fontes=[],
            correlation_id=correlation_id,
            status_fluxo='SEM_EVIDENCIA_BLOQUEADO',
            engine=engine,
            avisos=[
                'Resposta bloqueada por ausência de fontes recuperadas.',
                'Inclua documentos no payload ou configure REQSYS_RAG_DOCUMENTS_PATH.',
            ],
        )

    bullets = '\n'.join(f'- {fonte.trecho}' for fonte in fontes)
    resposta = (
        'Resposta baseada exclusivamente nas fontes recuperadas:\n'
        f'{bullets}\n\n'
        'Validação: confirme as fontes antes de usar como decisão operacional definitiva.'
    )
    logger.info('rag_com_fontes correlation_id=%s fontes=%s engine=%s', correlation_id, len(fontes), engine)
    return RespostaRAG(
        resposta=resposta,
        fontes=fontes,
        correlation_id=correlation_id,
        status_fluxo='COM_FONTES',
        engine=engine,
        avisos=['Modo governado: resposta exige fonte e aplica mascaramento básico de PII.'],
    )
