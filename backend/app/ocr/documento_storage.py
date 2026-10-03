"""Proteção de conteúdo sensível extraído de documentos de demanda.

O módulo reutiliza o ``OcrDataProtector`` do bounded context OCR e mantém o
conteúdo sensível dentro dos campos já existentes da tabela, evitando uma
segunda implementação criptográfica e uma alteração de esquema apenas para
proteger os dados.
"""
from __future__ import annotations

import json
from typing import Any

from app.ocr.storage import OcrDataProtector

_SCHEMA_VERSION = '1.0.0'
_ENCRYPTION = 'AES-256-GCM'


class DocumentoProtegidoInvalido(RuntimeError):
    """Conteúdo ausente de proteção, corrompido ou incompatível com a chave."""


def _aad(sha256: str, campo: str) -> str:
    return f'documento-demanda:{sha256}:{campo}'


def _proteger_valor(
    protector: OcrDataProtector,
    valor: Any,
    *,
    sha256: str,
    campo: str,
) -> str:
    ciphertext = protector.proteger({'valor': valor}, aad=_aad(sha256, campo))
    return json.dumps(
        {
            'schema_version': _SCHEMA_VERSION,
            'encryption': _ENCRYPTION,
            'key_version': protector.key_version,
            'ciphertext': ciphertext,
        },
        ensure_ascii=False,
        separators=(',', ':'),
    )


def _revelar_valor(
    protector: OcrDataProtector,
    blob: str,
    *,
    sha256: str,
    campo: str,
) -> Any:
    try:
        envelope = json.loads(blob)
    except (TypeError, json.JSONDecodeError) as exc:
        raise DocumentoProtegidoInvalido('conteúdo de documento não está protegido') from exc

    if not isinstance(envelope, dict):
        raise DocumentoProtegidoInvalido('conteúdo de documento não está protegido')
    if envelope.get('schema_version') != _SCHEMA_VERSION:
        raise DocumentoProtegidoInvalido('versão do envelope protegido não suportada')
    if envelope.get('encryption') != _ENCRYPTION:
        raise DocumentoProtegidoInvalido('algoritmo de proteção do documento não suportado')
    if envelope.get('key_version') != protector.key_version:
        raise DocumentoProtegidoInvalido('versão da chave do documento incompatível')

    ciphertext = envelope.get('ciphertext')
    if not isinstance(ciphertext, str) or not ciphertext:
        raise DocumentoProtegidoInvalido('ciphertext do documento ausente')

    try:
        payload = protector.revelar(ciphertext, aad=_aad(sha256, campo))
    except RuntimeError as exc:
        raise DocumentoProtegidoInvalido('conteúdo de documento não pôde ser revelado') from exc

    if not isinstance(payload, dict) or 'valor' not in payload:
        raise DocumentoProtegidoInvalido('payload protegido do documento inválido')
    return payload['valor']


def proteger_texto_documento(
    protector: OcrDataProtector,
    texto: str,
    *,
    sha256: str,
) -> str:
    if not texto:
        return ''
    return _proteger_valor(protector, texto, sha256=sha256, campo='texto_extraido')


def revelar_texto_documento(
    protector: OcrDataProtector,
    blob: str,
    *,
    sha256: str,
) -> str:
    if not blob:
        return ''
    valor = _revelar_valor(protector, blob, sha256=sha256, campo='texto_extraido')
    if not isinstance(valor, str):
        raise DocumentoProtegidoInvalido('texto protegido do documento inválido')
    return valor


def proteger_candidatos_documento(
    protector: OcrDataProtector,
    candidatos_json: str,
    *,
    sha256: str,
) -> str:
    if not candidatos_json or candidatos_json == '[]':
        return '[]'
    try:
        candidatos = json.loads(candidatos_json)
    except json.JSONDecodeError as exc:
        raise ValueError('candidatos_json inválido') from exc
    if not isinstance(candidatos, list):
        raise ValueError('candidatos_json deve representar uma lista')
    if not candidatos:
        return '[]'
    return _proteger_valor(protector, candidatos, sha256=sha256, campo='candidatos')


def revelar_candidatos_documento(
    protector: OcrDataProtector,
    blob: str,
    *,
    sha256: str,
) -> list[dict[str, Any]]:
    if not blob or blob == '[]':
        return []
    valor = _revelar_valor(protector, blob, sha256=sha256, campo='candidatos')
    if not isinstance(valor, list) or not all(isinstance(item, dict) for item in valor):
        raise DocumentoProtegidoInvalido('candidatos protegidos do documento inválidos')
    return valor
