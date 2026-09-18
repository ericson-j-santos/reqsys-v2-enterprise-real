import httpx
import pytest

from scripts.integration_excel_sql_sharepoint_e2e_cleanup_oidc import (
    CleanupError,
    retry,
    retryable_dataverse,
)


def test_retry_recupera_falha_transitoria_sem_repetir_apos_sucesso():
    calls = {"count": 0}

    def operation():
        calls["count"] += 1
        if calls["count"] < 3:
            raise httpx.ReadTimeout("transient")
        return "ok"

    assert retry(
        operation,
        attempts=4,
        delay_seconds=0,
        retryable=lambda exc: isinstance(exc, httpx.RequestError),
    ) == "ok"
    assert calls["count"] == 3


def test_retry_falha_fechado_quando_erro_nao_e_retryable():
    with pytest.raises(CleanupError, match="permanente"):
        retry(
            lambda: (_ for _ in ()).throw(CleanupError("permanente")),
            attempts=3,
            delay_seconds=0,
            retryable=lambda exc: False,
        )


def test_retryable_dataverse_aceita_timeout_e_rejeita_validacao():
    assert retryable_dataverse(httpx.ReadTimeout("timeout")) is True
    assert retryable_dataverse(CleanupError("validacao")) is False
