from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "backend" / "app" / "services" / "movimento_email" / "sql" / "views"
DEV = ROOT / "backend" / "app" / "services" / "movimento_email" / "sql" / "dev"

EXPECTED_TABLES = {
    "V2__vw_prospeccao_movimento_fechamento_diario.sql": "movimento_src.fechamento_diario",
    "V2__vw_prospeccao_movimento_pendencias_cadastro.sql": "movimento_src.pendencias_cadastro",
    "V2__vw_prospeccao_movimento_pendencias_historicas.sql": "movimento_src.pendencias_historicas",
    "V2__vw_prospeccao_movimento_pendencias_observacao.sql": "movimento_src.pendencias_observacao",
}


def test_v2_uses_real_source_tables_and_not_stub() -> None:
    for filename, table in EXPECTED_TABLES.items():
        sql = (VIEWS / filename).read_text(encoding="utf-8")
        assert table in sql
        assert "WHERE 1 = 0" not in sql
        assert "CREATE OR ALTER VIEW" in sql


def test_dev_source_schema_has_all_four_tables() -> None:
    sql = (DEV / "V1__source_schema.sql").read_text(encoding="utf-8")
    for table in EXPECTED_TABLES.values():
        assert table in sql
    assert "CREATE LOGIN" not in sql.upper()
    assert "CREATE USER" not in sql.upper()


def test_e2e_seed_is_explicitly_synthetic_and_idempotent() -> None:
    sql = (DEV / "V1__seed_e2e.sql").read_text(encoding="utf-8")
    assert "REQSYS_V2_E2E" in sql
    assert "2099-12-31" in sql
    assert sql.count("DELETE FROM movimento_src.") == 4


def test_manifest_v2_checksums_match_files() -> None:
    manifest = json.loads((VIEWS / "MANIFEST.json").read_text(encoding="utf-8"))
    v2 = next(item for item in manifest["versoes"] if item["versao"] == "V2")
    for entry in [*v2["arquivos"], v2["rollback"]]:
        digest = hashlib.sha256((VIEWS / entry["arquivo"]).read_bytes()).hexdigest()
        assert digest == entry["sha256"]
