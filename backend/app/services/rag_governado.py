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

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.pii_masking import mascarar_pii
from app.models.rag_chunk_embedding import RagChunkEmbedding
from app.services.llm_provider import LLMGateway

logger = logging.getLogger('reqsys.rag')

ENGINE_MEMORIA = 'semantic-hash-embedding+memory-vector-store-v1'
ENGINE_PERSISTIDO = 'semantic-hash-embedding+postgres-vector-store-v1'

PROVIDER_HASH_LOCAL = 'hash-local-256'
_METODOS_EMBEDDING_POR_PROVIDER = {
    'openai': 'gerar_embeddings_openai',
    'gemini': 'gerar_embeddings_gemini',
}
# Gemini oferece camada gratuita para embeddings (text-embedding-004); usado quando
# REQSYS_RAG_EMBEDDING_MODEL nao e configurado explicitamente para o provider ativo.
_MODELO_EMBEDDING_PADRAO_POR_PROVIDER = {
    'openai': 'text-embedding-3-small',
    'gemini': 'text-embedding-004',
}

_SYSTEM_PROMPT_LLM_RAG = (
    'Você é um assistente corporativo governado. Responda exclusivamente com base nas fontes '
    'fornecidas pelo usuário. Se as fontes não cobrirem a pergunta, diga explicitamente que não '
    'há evidência suficiente. Nunca invente informação fora das fontes.'
)
_METODOS_LLM_POR_PROVIDER = {
    'openai': 'gerar_openai',
    'claude': 'gerar_claude',
    'groq': 'gerar_groq',
    'gemini': 'gerar_gemini',
}


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


def resolver_provider_embedding_ativo() -> str:
    """Provider de embedding configurado, ou PROVIDER_HASH_LOCAL se ausente/nao suportado."""
    provider = (settings.reqsys_rag_embedding_provider or '').strip().lower()
    if not provider:
        return PROVIDER_HASH_LOCAL
    if provider not in _METODOS_EMBEDDING_POR_PROVIDER or not settings.reqsys_rag_embedding_api_key:
        logger.warning('rag_embedding_provider_indisponivel provider=%s', provider)
        return PROVIDER_HASH_LOCAL
    return provider


def _embeddings_lote(textos: list[str], *, provider: str, gateway: LLMGateway | None = None) -> list[list[float]]:
    """Embeda todos os textos com UM provider so - nunca mistura espacos vetoriais no mesmo lote."""
    if not textos:
        return []
    if provider == PROVIDER_HASH_LOCAL:
        return [_embedding_local(texto) for texto in textos]
    metodo = _METODOS_EMBEDDING_POR_PROVIDER[provider]
    gw = gateway or LLMGateway()
    vetores = getattr(gw, metodo)(
        api_key=settings.reqsys_rag_embedding_api_key,
        model=settings.reqsys_rag_embedding_model or _MODELO_EMBEDDING_PADRAO_POR_PROVIDER.get(provider, ''),
        textos=textos,
    )
    if len(vetores) != len(textos):
        raise RuntimeError(f'provider {provider} retornou {len(vetores)} embeddings para {len(textos)} textos')
    return vetores


def _embeddings_lote_com_fallback(textos: list[str], *, gateway: LLMGateway | None = None) -> tuple[list[list[float]], str]:
    """Como _embeddings_lote, mas cai para hash local no lote inteiro se o provider externo falhar.

    Fallback e sempre por lote inteiro, nunca por item - misturar vetores de dois espacos
    diferentes dentro do mesmo indice produziria scores de cosseno sem sentido.
    """
    provider = resolver_provider_embedding_ativo()
    if provider == PROVIDER_HASH_LOCAL:
        return _embeddings_lote(textos, provider=provider), provider
    try:
        return _embeddings_lote(textos, provider=provider, gateway=gateway), provider
    except (RuntimeError, requests.RequestException, KeyError, IndexError, ValueError) as exc:
        logger.warning('rag_embedding_externo_falhou provider=%s erro=%s', provider, exc)
        return _embeddings_lote(textos, provider=PROVIDER_HASH_LOCAL), PROVIDER_HASH_LOCAL


class VectorStoreMemoria:
    def __init__(self, chunks: list[ChunkRAG], *, gateway: LLMGateway | None = None) -> None:
        self._gateway = gateway
        textos = [f'{chunk.titulo} {chunk.conteudo}' for chunk in chunks]
        vetores, self._provider = _embeddings_lote_com_fallback(textos, gateway=gateway)
        self._itens = list(zip(chunks, vetores, strict=True))

    def buscar(self, pergunta: str, top_k: int = 4) -> list[FonteRAG]:
        if not self._itens:
            return []
        try:
            consulta = _embeddings_lote([pergunta], provider=self._provider, gateway=self._gateway)[0]
        except (RuntimeError, requests.RequestException, KeyError, IndexError, ValueError) as exc:
            # Os chunks ja estao no espaco vetorial de self._provider; cair para hash local
            # aqui misturaria dois espacos incompativeis e geraria scores sem sentido, entao
            # o mais seguro e nao inventar fontes.
            logger.warning('rag_embedding_consulta_falhou provider=%s erro=%s', self._provider, exc)
            return []
        resultados: list[FonteRAG] = []
        for chunk, vetor in self._itens:
            score = _cosseno(consulta, vetor)
            if score <= 0:
                continue
            resultados.append(FonteRAG(id=chunk.id, titulo=chunk.titulo, origem=chunk.origem, score=round(score, 4), trecho=chunk.conteudo[:520]))
        return sorted(resultados, key=lambda fonte: fonte.score, reverse=True)[:top_k]


def recuperar_fontes_semanticas(pergunta: str, documentos: list[DocumentoRAG], top_k: int = 4) -> list[FonteRAG]:
    return VectorStoreMemoria(criar_chunks(documentos)).buscar(pergunta, top_k=top_k)


def indexar_chunks_persistentes(
    db: Session,
    documentos: list[DocumentoRAG],
    *,
    tamanho: int = 900,
    sobreposicao: int = 120,
    gateway: LLMGateway | None = None,
) -> int:
    """Persiste chunks + embeddings em rag_chunk_embeddings (upsert por chunk_id)."""
    chunks = criar_chunks(documentos, tamanho=tamanho, sobreposicao=sobreposicao)
    if not chunks:
        return 0
    textos = [f'{chunk.titulo} {chunk.conteudo}' for chunk in chunks]
    vetores, provider = _embeddings_lote_com_fallback(textos, gateway=gateway)
    existentes = {
        item.chunk_id: item
        for item in db.execute(select(RagChunkEmbedding).where(RagChunkEmbedding.documento_id.in_({c.documento_id for c in chunks}))).scalars()
    }
    persistidos = 0
    for chunk, vetor in zip(chunks, vetores, strict=True):
        item = existentes.get(chunk.id)
        if item is None:
            db.add(
                RagChunkEmbedding(
                    chunk_id=chunk.id,
                    documento_id=chunk.documento_id,
                    titulo=chunk.titulo,
                    origem=chunk.origem,
                    conteudo=chunk.conteudo,
                    indice=chunk.indice,
                    versao=chunk.versao,
                    embedding=vetor,
                    embedding_provider=provider,
                )
            )
        else:
            item.titulo = chunk.titulo
            item.origem = chunk.origem
            item.conteudo = chunk.conteudo
            item.versao = chunk.versao
            item.embedding = vetor
            item.embedding_provider = provider
        persistidos += 1
    db.commit()
    return persistidos


def recuperar_fontes_semanticas_persistidas(db: Session, pergunta: str, top_k: int = 4, *, gateway: LLMGateway | None = None) -> list[FonteRAG]:
    # Se a chamada externa falhar aqui, cai para hash local e filtra so linhas indexadas com
    # hash local - nunca compara a consulta contra embeddings de um provider diferente.
    vetores, provider_usado = _embeddings_lote_com_fallback([pergunta], gateway=gateway)
    consulta = vetores[0]
    stmt = select(RagChunkEmbedding).where(RagChunkEmbedding.embedding_provider == provider_usado)
    resultados: list[FonteRAG] = []
    for item in db.execute(stmt).scalars():
        score = _cosseno(consulta, item.embedding)
        if score <= 0:
            continue
        resultados.append(FonteRAG(id=item.chunk_id, titulo=item.titulo, origem=item.origem, score=round(score, 4), trecho=item.conteudo[:520]))
    return sorted(resultados, key=lambda fonte: fonte.score, reverse=True)[:top_k]


def _montar_prompt_llm(pergunta: str, fontes: list[FonteRAG]) -> str:
    contexto = '\n\n'.join(f'[fonte {indice}, score={fonte.score:.4f}] {fonte.trecho}' for indice, fonte in enumerate(fontes, start=1))
    return f'Pergunta: {pergunta}\n\nFontes recuperadas:\n{contexto}\n\nResponda com base apenas nessas fontes.'


def gerar_resposta_llm(pergunta: str, fontes: list[FonteRAG], *, gateway: LLMGateway | None = None) -> str | None:
    """Gera a resposta em linguagem natural via LLM externo, se REQSYS_RAG_LLM_PROVIDER/_API_KEY estiverem configurados.

    Retorna None (nunca levanta) quando não há credencial, o provider não é suportado ou a
    chamada falha — o chamador deve cair para a resposta determinística por fontes nesse caso.
    """
    provider = (settings.reqsys_rag_llm_provider or '').strip().lower()
    api_key = settings.reqsys_rag_llm_api_key
    if not provider or not api_key or not fontes:
        return None
    metodo = _METODOS_LLM_POR_PROVIDER.get(provider)
    if metodo is None:
        logger.warning('rag_llm_provider_nao_suportado provider=%s', provider)
        return None
    gw = gateway or LLMGateway()
    try:
        return getattr(gw, metodo)(
            api_key=api_key,
            model=settings.reqsys_rag_llm_model or '',
            prompt=_montar_prompt_llm(pergunta, fontes),
            system_prompt=_SYSTEM_PROMPT_LLM_RAG,
        )
    except (RuntimeError, requests.RequestException, KeyError, IndexError) as exc:
        logger.warning('rag_llm_geracao_falhou provider=%s erro=%s', provider, exc)
        return None


def _montar_resposta(pergunta_mascarada: str, fontes: list[FonteRAG], *, correlation_id: str, engine: str) -> RespostaRAG:
    if not fontes:
        logger.info('rag_sem_evidencia correlation_id=%s engine=%s', correlation_id, engine)
        return RespostaRAG(resposta='Não há evidência suficiente nas fontes disponíveis para responder com segurança.', fontes=[], correlation_id=correlation_id, status_fluxo='SEM_EVIDENCIA_BLOQUEADO', engine=engine, avisos=['Resposta bloqueada por ausência de fontes recuperadas.', 'Inclua documentos no payload ou configure REQSYS_RAG_DOCUMENTS_PATH.'])

    bullets = '\n'.join(f'- [{fonte.score:.4f}] {fonte.trecho}' for fonte in fontes)
    resposta_llm = gerar_resposta_llm(pergunta_mascarada, fontes)
    if resposta_llm:
        provider = (settings.reqsys_rag_llm_provider or '').strip().lower()
        resposta = f'{resposta_llm}\n\nFontes utilizadas:\n{bullets}'
        engine_final = f'{engine}+llm-{provider}'
        avisos = ['Modo governado: resposta gerada por LLM exclusivamente a partir das fontes recuperadas.', f'Provider: {provider}.']
    else:
        resposta = f'Resposta baseada exclusivamente nas fontes recuperadas:\n{bullets}\n\nValidação: confirme as fontes antes de usar como decisão operacional definitiva.'
        engine_final = engine
        avisos = ['Modo governado: recuperação vetorial local, fonte obrigatória e mascaramento básico de PII.']

    logger.info('rag_com_fontes correlation_id=%s fontes=%s engine=%s', correlation_id, len(fontes), engine_final)
    return RespostaRAG(resposta=resposta, fontes=fontes, correlation_id=correlation_id, status_fluxo='COM_FONTES', engine=engine_final, avisos=avisos)


def responder_rag_governado(pergunta: str, documentos: list[DocumentoRAG], *, top_k: int = 4, correlation_id: str | None = None) -> RespostaRAG:
    correlation_id = correlation_id or gerar_correlation_id()
    pergunta_mascarada = mascarar_pii(pergunta.strip())
    fontes = recuperar_fontes_semanticas(pergunta_mascarada, documentos, top_k=top_k)
    return _montar_resposta(pergunta_mascarada, fontes, correlation_id=correlation_id, engine=ENGINE_MEMORIA)


def responder_rag_governado_persistido(db: Session, pergunta: str, *, top_k: int = 4, correlation_id: str | None = None) -> RespostaRAG:
    correlation_id = correlation_id or gerar_correlation_id()
    pergunta_mascarada = mascarar_pii(pergunta.strip())
    fontes = recuperar_fontes_semanticas_persistidas(db, pergunta_mascarada, top_k=top_k)
    return _montar_resposta(pergunta_mascarada, fontes, correlation_id=correlation_id, engine=ENGINE_PERSISTIDO)
