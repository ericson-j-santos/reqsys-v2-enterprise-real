from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.pii_masking import mascarar_pii

logger = logging.getLogger('reqsys.rag')


@dataclass(frozen=True)
class DocumentoRAG:
    id: str
    titulo: str
    conteudo: str
    origem: str = 'payload'


@dataclass(frozen=True)
class ChunkRAG:
    id: str
    documento_id: str
    titulo: str
    origem: str
    conteudo: str
    indice: int
    versao: str


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
            documentos.append(DocumentoRAG(id=arquivo.stem, titulo=arquivo.name, conteudo=conteudo, origem=str(arquivo.relative_to(raiz))))
    return documentos


def _termos(texto: str) -> list[str]:
    return re.findall(r'[a-zA-ZÀ-ÿ0-9_]{3,}', texto.lower())


def criar_chunks(documentos: list[DocumentoRAG], *, tamanho: int = 900, sobreposicao: int = 120) -> list[ChunkRAG]:
    if tamanho < 100 or sobreposicao < 0 or sobreposicao >= tamanho:
        raise ValueError('Configuracao de chunking invalida')
    chunks: list[ChunkRAG] = []
    passo = tamanho - sobreposicao
    for documento in documentos:
        texto = documento.conteudo.strip()
        versao = hashlib.sha256(texto.encode('utf-8')).hexdigest()[:16]
        for indice, inicio in enumerate(range(0, len(texto), passo)):
            conteudo = texto[inicio:inicio + tamanho].strip()
            if not conteudo:
                continue
            chunks.append(ChunkRAG(id=f'{documento.id}:{versao}:{indice}', documento_id=documento.id, titulo=documento.titulo, origem=documento.origem, conteudo=conteudo, indice=indice, versao=versao))
            if inicio + tamanho >= len(texto):
                break
    return chunks


def _embedding_local(texto: str, dimensoes: int = 256) -> list[float]:
    vetor = [0.0] * dimensoes
    for termo, frequencia in Counter(_termos(texto)).items():
        digest = hashlib.sha256(termo.encode('utf-8')).digest()
        posicao = int.from_bytes(digest[:4], 'big') % dimensoes
        sinal = 1.0 if digest[4] % 2 == 0 else -1.0
        vetor[posicao] += sinal * (1.0 + math.log(frequencia))
    norma = math.sqrt(sum(valor * valor for valor in vetor))
    return [valor / norma for valor in vetor] if norma else vetor


def _cosseno(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class VectorStoreMemoria:
    def __init__(self, chunks: list[ChunkRAG]) -> None:
        self._itens = [(chunk, _embedding_local(f'{chunk.titulo} {chunk.conteudo}')) for chunk in chunks]

    def buscar(self, pergunta: str, top_k: int = 4) -> list[FonteRAG]:
        consulta = _embedding_local(pergunta)
        resultados: list[FonteRAG] = []
        for chunk, vetor in self._itens:
            score = _cosseno(consulta, vetor)
            if score <= 0:
                continue
            resultados.append(FonteRAG(id=chunk.id, titulo=chunk.titulo, origem=chunk.origem, score=round(score, 4), trecho=chunk.conteudo[:520]))
        return sorted(resultados, key=lambda fonte: fonte.score, reverse=True)[:top_k]


def recuperar_fontes_semanticas(pergunta: str, documentos: list[DocumentoRAG], top_k: int = 4) -> list[FonteRAG]:
    return VectorStoreMemoria(criar_chunks(documentos)).buscar(pergunta, top_k=top_k)


def responder_rag_governado(pergunta: str, documentos: list[DocumentoRAG], *, top_k: int = 4, correlation_id: str | None = None) -> RespostaRAG:
    correlation_id = correlation_id or gerar_correlation_id()
    pergunta_mascarada = mascarar_pii(pergunta.strip())
    fontes = recuperar_fontes_semanticas(pergunta_mascarada, documentos, top_k=top_k)
    engine = 'semantic-hash-embedding+memory-vector-store-v1'

    if not fontes:
        logger.info('rag_sem_evidencia correlation_id=%s engine=%s', correlation_id, engine)
        return RespostaRAG(resposta='Não há evidência suficiente nas fontes disponíveis para responder com segurança.', fontes=[], correlation_id=correlation_id, status_fluxo='SEM_EVIDENCIA_BLOQUEADO', engine=engine, avisos=['Resposta bloqueada por ausência de fontes recuperadas.', 'Inclua documentos no payload ou configure REQSYS_RAG_DOCUMENTS_PATH.'])

    bullets = '\n'.join(f'- [{fonte.score:.4f}] {fonte.trecho}' for fonte in fontes)
    resposta = f'Resposta baseada exclusivamente nas fontes recuperadas:\n{bullets}\n\nValidação: confirme as fontes antes de usar como decisão operacional definitiva.'
    logger.info('rag_com_fontes correlation_id=%s fontes=%s engine=%s', correlation_id, len(fontes), engine)
    return RespostaRAG(resposta=resposta, fontes=fontes, correlation_id=correlation_id, status_fluxo='COM_FONTES', engine=engine, avisos=['Modo governado: recuperação vetorial local, fonte obrigatória e mascaramento básico de PII.'])
