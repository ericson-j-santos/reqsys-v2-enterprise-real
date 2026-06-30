from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger('reqsys.ollama_gateway.audit')

_PII_PATTERNS = [
    re.compile(r'(senha|password|api[_-]?key)\s*[:=]', re.I),
    re.compile(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b'),
]


def mascarar(texto: str, limite: int = 200) -> str:
    resumo = texto[:limite]
    for padrao in _PII_PATTERNS:
        resumo = padrao.sub('[REDACTED]', resumo)
    if 'senha' in texto.lower() or 'password' in texto.lower():
        resumo = '[REDACTED]'
    return resumo


def auditar(evento: str, payload: dict[str, Any]) -> None:
    seguro = {**payload}
    for chave in ('prompt', 'contexto', 'entrada', 'response'):
        if chave in seguro and isinstance(seguro[chave], str):
            seguro[chave] = mascarar(seguro[chave])
    logger.info('%s %s', evento, json.dumps(seguro, ensure_ascii=False, sort_keys=True))
