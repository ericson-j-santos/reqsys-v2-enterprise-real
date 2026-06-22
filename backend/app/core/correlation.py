from contextvars import ContextVar
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
