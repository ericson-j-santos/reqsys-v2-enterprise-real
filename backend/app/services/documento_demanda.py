from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace

TIPOS_OCR_DOCUMENTO = {
    'application/pdf',
    'image/png',
    'image/jpeg',
}

TIPOS_SUPORTADOS = {
    *TIPOS_OCR_DOCUMENTO,
    'text/plain',
    'text/csv',
    'application/json',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class CandidatoDemanda:
    tipo: str
    texto: str
    confianca: float
    requer_validacao_humana: bool = True
    pagina: int | None = None


def validar_upload(*, nome_arquivo: str, content_type: str, conteudo: bytes) -> None:
    if not nome_arquivo.strip():
        raise ValueError('nome_arquivo obrigatório')
    if content_type not in TIPOS_SUPORTADOS:
        raise ValueError('tipo de arquivo não suportado')
    if not conteudo:
        raise ValueError('arquivo vazio')
    if len(conteudo) > MAX_UPLOAD_BYTES:
        raise ValueError('arquivo excede limite de 10 MB')


def calcular_sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def extrair_texto_basico(content_type: str, conteudo: bytes) -> str:
    if content_type in {'text/plain', 'text/csv', 'application/json'}:
        return conteudo.decode('utf-8', errors='replace').strip()
    return ''


def classificar_candidatos(texto: str) -> list[CandidatoDemanda]:
    candidatos: list[CandidatoDemanda] = []
    sentencas = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', texto) if s.strip()]
    for sentenca in sentencas[:200]:
        lower = sentenca.lower()
        if any(chave in lower for chave in ('deve ', 'deverá ', 'precisa ', 'necessário ', 'obrigatório ')):
            tipo = 'POSSIVEL_REQUISITO'
        elif any(chave in lower for chave in ('somente ', 'apenas ', 'não pode ', 'proibido ', 'permitido ')):
            tipo = 'POSSIVEL_REGRA_NEGOCIO'
        elif any(chave in lower for chave in ('segundo', 'até ', 'ms', 'disponibilidade', 'latência')):
            tipo = 'POSSIVEL_REQUISITO_NAO_FUNCIONAL'
        else:
            continue
        candidatos.append(CandidatoDemanda(tipo=tipo, texto=sentenca[:2000], confianca=0.70))
    return candidatos


def classificar_candidatos_por_paginas(
    paginas: list[tuple[int, str, float]],
) -> list[CandidatoDemanda]:
    candidatos: list[CandidatoDemanda] = []
    for pagina, texto, confianca_ocr in paginas:
        for item in classificar_candidatos(texto):
            candidatos.append(
                replace(
                    item,
                    pagina=pagina,
                    confianca=round(min(item.confianca, max(0.0, confianca_ocr)), 6),
                )
            )
    return candidatos


def serializar_candidatos(candidatos: list[CandidatoDemanda]) -> str:
    return json.dumps([c.__dict__ for c in candidatos], ensure_ascii=False, sort_keys=True)
