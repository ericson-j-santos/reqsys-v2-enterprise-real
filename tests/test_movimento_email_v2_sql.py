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


def test_dev_ssrs_rdl_rds_are_safe_and_point_to_dev_database() -> None:
    ssrs = ROOT / "backend" / "app" / "services" / "movimento_email" / "ssrs" / "dev"
    rds = (ssrs / "MovimentoEmailDev.rds").read_text(encoding="utf-8")
    rdl = (ssrs / "ProspecaoMovimentoDev.rdl").read_text(encoding="utf-8")
    combined = (rds + "\n" + rdl).lower()

    assert "data source=localhost" in combined
    assert "initial catalog=reqsysmovimentodev" in combined
    assert "integratedsecurity>true" in combined.replace(" ", "")
    assert "password=" not in combined
    assert "pwd=" not in combined
    assert "user id=" not in combined
    for table in EXPECTED_TABLES.values():
        view_name = table.replace("movimento_src.", "vw_prospeccao_movimento_")
        assert view_name not in rdl  # evita confundir tabela-fonte com nome da view
    for filename in EXPECTED_TABLES:
        view = filename.removeprefix("V2__").removesuffix(".sql")
        assert f"dbo.{view}" in rdl
