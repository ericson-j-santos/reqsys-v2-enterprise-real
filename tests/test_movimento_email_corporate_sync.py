from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path("scripts/sincronizar_movimento_email_corporate.py")
SPEC = importlib.util.spec_from_file_location("movimento_email_corporate", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_source_dsn_requires_encryption_and_valid_certificate() -> None:
    module.validate_source_dsn(
        "Driver={ODBC Driver 18 for SQL Server};Server=sql;Database=db;"
        "UID=u;PWD=p;Encrypt=yes;TrustServerCertificate=no;"
    )

    with pytest.raises(RuntimeError, match="requires_encrypt"):
        module.validate_source_dsn(
            "Driver={ODBC Driver 18 for SQL Server};Server=sql;Database=db;"
            "UID=u;PWD=p;Encrypt=no;"
        )

    with pytest.raises(RuntimeError, match="cannot_trust_server_certificate"):
        module.validate_source_dsn(
            "Driver={ODBC Driver 18 for SQL Server};Server=sql;Database=db;"
            "UID=u;PWD=p;Encrypt=yes;TrustServerCertificate=yes;"
        )


def test_default_mapping_is_exactly_four_datasets() -> None:
    mapping = module.load_mapping(None)
    assert set(mapping) == {
        "fechamento_diario",
        "pendencias_cadastro",
        "pendencias_historicas",
        "pendencias_observacao",
    }
    assert mapping["pendencias_cadastro"]["target_object"] == "movimento_src.pendencias_cadastro"


def test_mapping_allows_real_object_names_without_changing_contract(tmp_path: Path) -> None:
    payload = {"datasets": json.loads(json.dumps(module.DEFAULT_MAPPING))}
    payload["datasets"]["fechamento_diario"]["source_object"] = "ssrs.vw_fechamento_real"
    path = tmp_path / "map.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    mapping = module.load_mapping(path)

    assert mapping["fechamento_diario"]["source_object"] == "ssrs.vw_fechamento_real"


def test_mapping_rejects_contract_drift(tmp_path: Path) -> None:
    payload = {"datasets": json.loads(json.dumps(module.DEFAULT_MAPPING))}
    payload["datasets"]["pendencias_cadastro"]["columns"] = ["protocolo"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="column_contract_mismatch"):
        module.load_mapping(path)


def test_payload_fingerprint_is_idempotent_and_sensitive_to_change() -> None:
    first = module.payload_fingerprint({"a": "1", "b": "2"}, "2026-09-18")
    same = module.payload_fingerprint({"b": "2", "a": "1"}, "2026-09-18")
    changed = module.payload_fingerprint({"a": "1", "b": "3"}, "2026-09-18")

    assert first == same
    assert changed != first


def test_read_secret_supports_host_protected_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret_file = tmp_path / "dsn.secret"
    secret_file.write_text("Driver=X;Encrypt=yes", encoding="utf-8")
    monkeypatch.delenv("MOVIMENTO_EMAIL_SOURCE_DSN", raising=False)
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_DSN_FILE", str(secret_file))

    assert module.read_secret("MOVIMENTO_EMAIL_SOURCE_DSN") == "Driver=X;Encrypt=yes"


def test_read_secret_rejects_ambiguous_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret_file = tmp_path / "dsn.secret"
    secret_file.write_text("file", encoding="utf-8")
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_DSN", "env")
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_DSN_FILE", str(secret_file))

    with pytest.raises(RuntimeError, match="ambiguous"):
        module.read_secret("MOVIMENTO_EMAIL_SOURCE_DSN")

def test_integrated_source_dsn_is_tls_readonly_and_passwordless() -> None:
    dsn = module.build_integrated_dsn(
        "sql-corp\\instance",
        "DB7008_CEPOC",
        driver="ODBC Driver 18 for SQL Server",
        source=True,
    )

    assert "Trusted_Connection=yes" in dsn
    assert "Encrypt=yes" in dsn
    assert "TrustServerCertificate=no" in dsn
    assert "ApplicationIntent=ReadOnly" in dsn
    assert "UID=" not in dsn and "PWD=" not in dsn
    module.validate_source_dsn(dsn)


def test_resolve_source_dsn_supports_integrated_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOVIMENTO_EMAIL_SOURCE_DSN", raising=False)
    monkeypatch.delenv("MOVIMENTO_EMAIL_SOURCE_DSN_FILE", raising=False)
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_SERVER", "sql-corp")
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_DATABASE", "DB7008_CEPOC")
    monkeypatch.setattr(module, "choose_driver", lambda: "ODBC Driver 18 for SQL Server")

    dsn = module.resolve_source_dsn()

    assert "Server=sql-corp" in dsn
    assert "Database=DB7008_CEPOC" in dsn
    assert "ApplicationIntent=ReadOnly" in dsn


def test_resolve_source_dsn_rejects_incomplete_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOVIMENTO_EMAIL_SOURCE_DSN", raising=False)
    monkeypatch.delenv("MOVIMENTO_EMAIL_SOURCE_DSN_FILE", raising=False)
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_SERVER", "sql-corp")
    monkeypatch.delenv("MOVIMENTO_EMAIL_SOURCE_DATABASE", raising=False)

    with pytest.raises(RuntimeError, match="source_integrated_endpoint_incomplete"):
        module.resolve_source_dsn()


def test_target_dsn_defaults_to_local_dev_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "MOVIMENTO_EMAIL_TARGET_DSN",
        "MOVIMENTO_EMAIL_TARGET_DSN_FILE",
        "MOVIMENTO_EMAIL_TARGET_SERVER",
        "MOVIMENTO_EMAIL_TARGET_DATABASE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(module, "choose_driver", lambda: "ODBC Driver 18 for SQL Server")

    dsn = module.resolve_target_dsn()

    assert "Server=localhost" in dsn
    assert "Database=ReqSysMovimentoDev" in dsn
    assert "Trusted_Connection=yes" in dsn
    assert "UID=" not in dsn and "PWD=" not in dsn


def test_target_integrated_endpoint_rejects_remote_or_non_dev() -> None:
    with pytest.raises(RuntimeError, match="must_be_local"):
        module.build_integrated_dsn(
            "remote-sql",
            "ReqSysMovimentoDev",
            driver="ODBC Driver 18 for SQL Server",
            source=False,
        )
    with pytest.raises(RuntimeError, match="must_end_with_dev"):
        module.build_integrated_dsn(
            "localhost",
            "ReqSysMovimentoProd",
            driver="ODBC Driver 18 for SQL Server",
            source=False,
        )


def test_source_configuration_rejects_mixed_explicit_and_integrated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_DSN", "Driver=X;Encrypt=yes;TrustServerCertificate=no")
    monkeypatch.delenv("MOVIMENTO_EMAIL_SOURCE_DSN_FILE", raising=False)
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_SERVER", "sql-corp")
    monkeypatch.setenv("MOVIMENTO_EMAIL_SOURCE_DATABASE", "db")

    with pytest.raises(RuntimeError, match="source_configuration_ambiguous"):
        module.resolve_source_dsn()


def test_target_configuration_rejects_mixed_explicit_and_integrated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOVIMENTO_EMAIL_TARGET_DSN", "Driver=X;Database=ReqSysMovimentoDev")
    monkeypatch.delenv("MOVIMENTO_EMAIL_TARGET_DSN_FILE", raising=False)
    monkeypatch.setenv("MOVIMENTO_EMAIL_TARGET_SERVER", "localhost")

    with pytest.raises(RuntimeError, match="target_configuration_ambiguous"):
        module.resolve_target_dsn()

