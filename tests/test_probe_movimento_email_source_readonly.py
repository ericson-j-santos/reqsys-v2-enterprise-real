from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path("scripts/probe_movimento_email_source_readonly.py")
SPEC = importlib.util.spec_from_file_location("probe_movimento_email_source_readonly", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_choose_driver_prefers_18_and_falls_back_to_17() -> None:
    assert module.choose_driver(["ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"]) == "ODBC Driver 18 for SQL Server"
    assert module.choose_driver(["ODBC Driver 17 for SQL Server"]) == "ODBC Driver 17 for SQL Server"
    with pytest.raises(RuntimeError, match="no_supported"):
        module.choose_driver(["SQL Server"])


def test_build_dsn_is_read_only_and_has_no_credentials() -> None:
    dsn = module.build_dsn("SQLHOST01", "DB7008_CEPOC", "ODBC Driver 17 for SQL Server")
    assert "Trusted_Connection=yes" in dsn
    assert "Encrypt=yes" in dsn
    assert "TrustServerCertificate=no" in dsn
    assert "ApplicationIntent=ReadOnly" in dsn
    assert "Driver={ODBC Driver 17 for SQL Server}" in dsn
    assert "UID=" not in dsn
    assert "PWD=" not in dsn


@pytest.mark.parametrize("server,database", [
    ("host;PWD=x", "DB7008_CEPOC"),
    ("SQLHOST01", "db;DROP DATABASE x"),
])
def test_build_dsn_rejects_injection(server: str, database: str) -> None:
    with pytest.raises(ValueError):
        module.build_dsn(server, database)


def test_hash_does_not_echo_value() -> None:
    value = "CCTCODADNT013"
    digest = module._hash(value)
    assert value not in digest
    assert len(digest) == 16


def test_build_dsn_rejects_unknown_driver() -> None:
    with pytest.raises(ValueError, match="invalid_driver"):
        module.build_dsn("SQLHOST01", "DB7008_CEPOC", "Legacy Driver")
