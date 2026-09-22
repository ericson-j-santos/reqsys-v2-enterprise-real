from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "provision_integration_excel_sql_sharepoint_dev_sql.py"
SPEC = importlib.util.spec_from_file_location("provision_sql_dev", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

DEFAULT_PROCEDURE = MODULE.DEFAULT_PROCEDURE
connection_string = MODULE.connection_string
procedure_sql = MODULE.procedure_sql
validate_database_name = MODULE.validate_database_name


def test_database_name_restrito_a_dev() -> None:
    assert validate_database_name("ReqSysIntegrationDev") == "ReqSysIntegrationDev"
    with pytest.raises(ValueError):
        validate_database_name("ReqSysIntegrationProd")
    with pytest.raises(ValueError):
        validate_database_name("ReqSys Integration Dev")


def test_connection_string_usa_identidade_integrada_sem_segredo() -> None:
    value = connection_string("ODBC Driver 18 for SQL Server", "localhost", "ReqSysIntegrationDev")
    assert "Trusted_Connection=yes" in value
    assert "TrustServerCertificate=yes" in value
    assert "Pwd=" not in value
    assert "Password=" not in value


def test_procedure_sql_cumpre_contrato_do_fluxo() -> None:
    sql = procedure_sql()
    assert f"CREATE OR ALTER PROCEDURE {DEFAULT_PROCEDURE}" in sql
    assert "@IdsJson nvarchar(max)" in sql
    assert "@CorrelationId uniqueidentifier" in sql
    assert "OPENJSON(@IdsJson)" in sql
    assert "integration.E2EIdentificadores" in sql
    assert "Identificador" in sql
