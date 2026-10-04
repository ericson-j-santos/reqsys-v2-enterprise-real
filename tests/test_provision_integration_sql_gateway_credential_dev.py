from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "provision_integration_sql_gateway_credential_dev.py"
SPEC = importlib.util.spec_from_file_location("gateway_credential", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_password_forte_sem_valor_fixo() -> None:
    first = MODULE.generate_password()
    second = MODULE.generate_password()
    assert len(first) >= 48
    assert first != second
    assert any(c.islower() for c in first)
    assert any(c.isupper() for c in first)
    assert any(c.isdigit() for c in first)
    assert any(c in "!@#$%^&*_-+=" for c in first)


def test_ddl_login_restrito_ao_login_dev() -> None:
    sql = MODULE.login_ddl("A1!safe'quote")
    assert f"CREATE LOGIN [{MODULE.LOGIN}]" in sql
    assert f"ALTER LOGIN [{MODULE.LOGIN}]" in sql
    assert "CHECK_POLICY = ON" in sql
    assert "CHECK_EXPIRATION = OFF" in sql
    assert "safe''quote" in sql


def test_ddl_usuario_tem_apenas_connect_e_execute() -> None:
    sql = MODULE.user_ddl()
    assert f"GRANT CONNECT TO [{MODULE.LOGIN}]" in sql
    assert f"GRANT EXECUTE ON OBJECT::{MODULE.PROCEDURE} TO [{MODULE.LOGIN}]" in sql
    forbidden = ("db_owner", "db_datareader", "db_datawriter", "CONTROL SERVER", "ALTER ANY")
    assert not any(marker in sql for marker in forbidden)


def test_connection_string_nao_e_usada_com_senha_vazia() -> None:
    value = MODULE.sql_connection_string("ODBC Driver 18 for SQL Server", "localhost", MODULE.DATABASE, "xY1!secret")
    assert "Uid=reqsys_e2e_gateway_dev" in value
    assert "Encrypt=yes" in value
    assert "TrustServerCertificate=yes" in value


class FakeCursor:
    def __init__(self) -> None:
        self.args = None

    def execute(self, *args):
        self.args = args
        return self

    def fetchone(self):
        return (MODULE.FIXTURE_ID, "fixture")


def test_probe_parametriza_correlation_id() -> None:
    cursor = FakeCursor()
    MODULE.execute_probe(cursor)
    assert cursor.args is not None
    sql, ids_json, correlation_id = cursor.args
    assert "@CorrelationId=?" in sql
    assert "NEWID()" not in sql
    assert MODULE.FIXTURE_ID in ids_json
    assert str(uuid.UUID(correlation_id)) == correlation_id
