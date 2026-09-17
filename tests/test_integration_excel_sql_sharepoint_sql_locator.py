from __future__ import annotations

# Revalidação não interativa do locator SQL DEV pelo Environment Secret governado.

import json

import pytest

from scripts.integration_excel_sql_sharepoint_sql_locator import (
    SqlLocatorError,
    digest,
    parameter_contract_ok,
    probe_sql,
    safe_error,
)


class FakeCursor:
    def __init__(self, context, parameters):
        self.context = context
        self.parameters = parameters
        self.step = 0

    def execute(self, *_args):
        self.step += 1
        return self

    def fetchone(self):
        return self.context

    def fetchall(self):
        return self.parameters


class FakeConnection:
    def __init__(self, context, parameters):
        self._cursor = FakeCursor(context, parameters)
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def test_parameter_contract_accepts_only_expected_signature():
    assert parameter_contract_ok([
        ("@IdsJson", "nvarchar", -1, False),
        ("@CorrelationId", "uniqueidentifier", 16, False),
    ]) is True

    assert parameter_contract_ok([
        ("@IdsJson", "varchar", -1, False),
        ("@CorrelationId", "uniqueidentifier", 16, False),
    ]) is False


def test_probe_resolves_exact_procedure_without_exposing_context():
    connection = FakeConnection(
        ("sql-dev.internal", "BancoNegocio", 1),
        [
            ("@IdsJson", "nvarchar", -1, False),
            ("@CorrelationId", "uniqueidentifier", 16, False),
        ],
    )

    result = probe_sql(
        "Driver=segredo;Pwd=nao-vazar",
        "integration.usp_ConsultarPorIdentificadores",
        connect=lambda *_args, **_kwargs: connection,
    )
    raw = json.dumps(result, ensure_ascii=False)

    assert result["procedure_exists"] is True
    assert result["parameter_contract_ok"] is True
    assert result["server_hash"] == digest("sql-dev.internal")
    assert result["database_hash"] == digest("BancoNegocio")
    assert "sql-dev.internal" not in raw
    assert "BancoNegocio" not in raw
    assert "nao-vazar" not in raw
    assert connection.closed is True


def test_probe_fails_closed_when_procedure_is_absent():
    connection = FakeConnection(("sql-dev.internal", "BancoNegocio", 0), [])

    with pytest.raises(SqlLocatorError, match="stored_procedure_ausente"):
        probe_sql(
            "Driver=segredo;Pwd=nao-vazar",
            "integration.usp_ConsultarPorIdentificadores",
            connect=lambda *_args, **_kwargs: connection,
        )

    assert connection.closed is True


def test_safe_error_never_serializes_connection_error_text():
    rendered = safe_error(RuntimeError("Driver=segredo;Pwd=nao-vazar"))
    assert rendered == "RuntimeError"
    assert "nao-vazar" not in rendered
