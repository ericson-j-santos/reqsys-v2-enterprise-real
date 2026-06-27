from contextvars import ContextVar
from typing import Mapping
from uuid import uuid4

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def gerar_correlation_id() -> str:
    return str(uuid4())


def obter_correlation_id() -> str:
    atual = _correlation_id.get()
    if atual:
        return atual
    novo = gerar_correlation_id()
    _correlation_id.set(novo)
    return novo


def definir_correlation_id(correlation_id: str | None) -> str:
    valor = correlation_id or gerar_correlation_id()
    _correlation_id.set(valor)
    return valor


def extrair_correlation_id_dos_headers(headers: Mapping[str, str]) -> str | None:
    normalizado = {str(key).lower(): value for key, value in headers.items()}
    for chave in ('x-correlation-id', 'x-request-id'):
        valor = normalizado.get(chave)
        if valor and str(valor).strip():
            return str(valor).strip()
    return None


def resolver_correlation_id(
    x_correlation_id: str | None = None,
    x_request_id: str | None = None,
) -> str:
    """Resolve correlation_id a partir de headers ou contexto já definido pelo middleware."""
    candidato = (x_correlation_id or x_request_id or "").strip() or None
    if candidato:
        return definir_correlation_id(candidato)
    atual = _correlation_id.get()
    if atual:
        return atual
    return definir_correlation_id(None)
