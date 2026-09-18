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
