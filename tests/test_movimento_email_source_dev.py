from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SQL=ROOT/"backend"/"app"/"services"/"movimento_email"/"sql"/"source_dev"
SSRS=ROOT/"backend"/"app"/"services"/"movimento_email"/"ssrs"/"dev"

def test_source_schema_has_four_legacy_tables_and_no_identity_creation():
    sql=(SOURCE_SQL/"V1__legacy_source_schema.sql").read_text(encoding="utf-8")
    for name in ("fechamento_diario","pendencias_cadastro","pendencias_historicas","pendencias_observacao"):
        assert f"legacy_ssrs.{name}" in sql
    upper=sql.upper()
    assert "CREATE LOGIN" not in upper
    assert "CREATE USER" not in upper

def test_seed_is_explicit_and_idempotent():
    sql=(SOURCE_SQL/"V1__seed_e2e.sql").read_text(encoding="utf-8")
    assert "REQSYS_SOURCE_E2E" in sql
    assert "2099-12-29" in sql
    assert sql.count("DELETE FROM legacy_ssrs.")==4

def test_source_rdl_rds_are_credential_free_and_point_to_source_database():
    rdl=(SSRS/"ProspecaoMovimentoSourceDev.rdl").read_text(encoding="utf-8")
    rds=(SSRS/"MovimentoEmailSourceDev.rds").read_text(encoding="utf-8")
    text=(rdl+"\n"+rds).lower()
    assert "data source=localhost" in text
    assert "initial catalog=reqsysmovimentosourcedev" in text
    assert "password=" not in text
    assert "pwd=" not in text
    assert "user id=" not in text
    for name in ("fechamento_diario","pendencias_cadastro","pendencias_historicas","pendencias_observacao"):
        assert f"legacy_ssrs.{name}" in rdl

def test_sync_is_fail_explicit_and_idempotent_by_source_tag():
    script=(ROOT/"scripts"/"sincronizar_movimento_email_source_dev.py").read_text(encoding="utf-8")
    assert "DELETE FROM movimento_src.{table} WHERE source_tag=?" in script
    assert "executemany" in script
    assert '"corporate_source_validated":False' in script
    assert '"secrets_used":False' in script
