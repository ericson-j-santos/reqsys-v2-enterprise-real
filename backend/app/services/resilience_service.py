from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from app.core.telemetry import log_erro, log_evento

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3


class ResilienceService:
    """Executa operação com tentativas limitadas e telemetria governada."""

    def executar_com_retry(self, nome_operacao: str, funcao: Callable[[], T], policy: RetryPolicy | None = None) -> T:
        regra = policy or RetryPolicy()
        ultimo_erro: Exception | None = None

        for tentativa in range(1, regra.max_attempts + 1):
            try:
                log_evento("retry.attempt", operation=nome_operacao, attempt=tentativa)
                resultado = funcao()
                log_evento("retry.success", operation=nome_operacao, attempt=tentativa)
                return resultado
            except Exception as exc:
                ultimo_erro = exc
                log_erro("retry.failure", exc, operation=nome_operacao, attempt=tentativa)

        log_erro("retry.exhausted", ultimo_erro or "erro desconhecido", operation=nome_operacao)
        raise ultimo_erro or RuntimeError(f"Operação {nome_operacao} falhou.")
