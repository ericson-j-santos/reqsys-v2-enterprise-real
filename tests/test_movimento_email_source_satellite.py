from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/movimento_email_source_satellite.py")
SPEC = importlib.util.spec_from_file_location("movimento_email_source_satellite", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class FakeCursor:
    def __init__(self) -> None:
        self.sql: list[str] = []
        self._rows = []

    def execute(self, sql: str):
        self.sql.append(sql)
        if "SERVERPROPERTY" in sql:
            self._rows = [("SQL01", "DB01", 0, 0, 0)]
        elif "INFORMATION_SCHEMA.TABLES" in sql:
            self._rows = [("CNS", "PROSPECCAO_MOVIMENTO", "BASE TABLE"), ("dbo", "other", "BASE TABLE")]
        elif "OBJECT_ID" in sql:
            self._rows = [(1,)]
        elif "dm_exec_describe_first_result_set" in sql:
            self._rows = [("NSU",), ("DemandaMotivo",)]
        else:
            self._rows = []
        return self

    def fetchone(self):
        return self._rows[0]

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self) -> None:
        self.closed = True


def test_build_dsn_is_passwordless_tls_and_readonly() -> None:
    candidate = module.Candidate("sql01", "db01", "test")
    dsn = module.build_dsn(candidate, "ODBC Driver 18 for SQL Server")

    assert "Trusted_Connection=yes" in dsn
    assert "Encrypt=yes" in dsn
    assert "TrustServerCertificate=no" in dsn
    assert "ApplicationIntent=ReadOnly" in dsn
    assert "UID=" not in dsn and "PWD=" not in dsn


def test_parse_env_candidates_and_dedupe() -> None:
    raw = '[{"server":"SQL01","database":"DB01"},{"server":"sql01","database":"db01"}]'
    parsed = module.parse_env_candidates(raw)

    deduped = module.dedupe_candidates(parsed)

    assert len(parsed) == 2
    assert len(deduped) == 1


def test_parse_env_candidates_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError, match="must_be_list"):
        module.parse_env_candidates('{"server":"sql01"}')


def test_probe_candidate_stops_before_sql_when_network_is_blocked() -> None:
    called = False

    def connect(_dsn: str):
        nonlocal called
        called = True
        return FakeConnection()

    result = module.probe_candidate(
        module.Candidate("sql01", "db01", "test"),
        network_fn=lambda _server: {"dns_resolved": False, "tcp_reachable": False},
        connect_fn=connect,
    )

    assert result["status"] == "blocked_network"
    assert result["write_attempted"] is False
    assert result["business_rows_read"] is False
    assert called is False


def test_probe_candidate_validates_metadata_without_business_rows() -> None:
    conn = FakeConnection()

    result = module.probe_candidate(
        module.Candidate("sql01", "db01", "test"),
        network_fn=lambda _server: {"dns_resolved": True, "tcp_reachable": True},
        connect_fn=lambda _dsn: conn,
        installed_drivers=["ODBC Driver 18 for SQL Server"],
    )

    assert result["passed"] is True
    assert result["expected_function_present"] is True
    assert result["expected_function_columns"] == ["NSU", "DemandaMotivo"]
    assert result["broad_write_role_detected"] is False
    assert result["write_attempted"] is False
    assert result["business_rows_read"] is False
    assert conn.closed is True
    assert all(sql.lstrip().upper().startswith("SELECT") for sql in conn.cursor_instance.sql)


def test_probe_candidate_blocks_broad_write_role() -> None:
    class WriteCursor(FakeCursor):
        def execute(self, sql: str):
            super().execute(sql)
            if "SERVERPROPERTY" in sql:
                self._rows = [("SQL01", "DB01", 0, 0, 1)]
            return self

    class WriteConnection(FakeConnection):
        def __init__(self) -> None:
            self.cursor_instance = WriteCursor()
            self.closed = False

    result = module.probe_candidate(
        module.Candidate("sql01", "db01", "test"),
        network_fn=lambda _server: {"dns_resolved": True, "tcp_reachable": True},
        connect_fn=lambda _dsn: WriteConnection(),
        installed_drivers=["ODBC Driver 18 for SQL Server"],
    )

    assert result["passed"] is False
    assert result["status"] == "blocked_write_privilege"


def test_run_reports_no_candidates_without_false_success() -> None:
    payload = module.run([])

    assert payload["status"] == "no_candidates"
    assert payload["source_validated"] is False
    assert payload["secret_exposed"] is False
    assert payload["production_touched"] is False
