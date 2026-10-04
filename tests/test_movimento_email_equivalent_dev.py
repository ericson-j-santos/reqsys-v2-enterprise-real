from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path("scripts/movimento_email_equivalent_dev.py")
SPEC = importlib.util.spec_from_file_location("movimento_email_equivalent_dev", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_equivalent_source_is_explicitly_dev_and_not_corporate() -> None:
    assert module.SOURCE_DB_DEFAULT.endswith("Dev")
    assert module.TARGET_DB_DEFAULT.endswith("Dev")
    assert module.SOURCE_TAG == "EQUIVALENT_DEV"
    assert module.DATA_REFERENCIA == dt.date(2099, 12, 30)


def test_local_guard_rejects_remote_server() -> None:
    assert module._safe_local_server("localhost") == "localhost"
    with pytest.raises(SystemExit, match="localhost"):
        module._safe_local_server("corporate-sql")


def test_database_guard_requires_dev_suffix() -> None:
    assert module._safe_dev_database("ReqSysMovimentoSourceDev") == "ReqSysMovimentoSourceDev"
    with pytest.raises(SystemExit, match="suffix_Dev"):
        module._safe_dev_database("ReqSysMovimentoProd")


def test_equivalent_fixture_has_expected_contract_counts() -> None:
    assert {name: len(cfg["rows"]) for name, cfg in module.DATASETS.items()} == {
        "fechamento_diario": 2,
        "pendencias_cadastro": 1,
        "pendencias_historicas": 1,
        "pendencias_observacao": 1,
    }


def test_fingerprint_is_stable_and_change_sensitive() -> None:
    rows = [("A", 1, dt.date(2099, 12, 30))]
    assert module._fingerprint(rows) == module._fingerprint(rows)
    assert module._fingerprint(rows) != module._fingerprint([("B", 1, dt.date(2099, 12, 30))])


def test_source_schema_is_separate_from_target_schema() -> None:
    sql = module.SOURCE_SCHEMA_SQL
    assert "legacy_ssrs.fechamento_diario" in sql
    assert "legacy_ssrs.pendencias_cadastro" in sql
    assert "legacy_ssrs.pendencias_historicas" in sql
    assert "legacy_ssrs.pendencias_observacao" in sql
    assert "movimento_src." not in sql


def test_source_tag_compatibility_is_preserved() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "_source_has_column" in script
    assert "WHERE source_tag = ? AND data_referencia = ?" in script
    assert "EQUIVALENT_DEV" in script
