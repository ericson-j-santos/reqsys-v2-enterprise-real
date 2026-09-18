from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OIDC_WORKFLOW = ROOT / ".github/workflows/integration-excel-sql-sharepoint-oidc-dev.yml"
LEGACY_WORKFLOW = ROOT / ".github/workflows/integration-excel-sql-sharepoint-e2e-dev.yml"


def _workflow_trigger_block(text: str) -> str:
    start = text.index("\non:\n") + 1
    end = text.index("\npermissions:\n", start)
    return text[start:end]


def test_oidc_e_canonico_na_main_e_tem_disparo_manual():
    text = OIDC_WORKFLOW.read_text(encoding="utf-8")
    trigger = _workflow_trigger_block(text)

    assert "workflow_dispatch:" in trigger
    assert "push:" in trigger
    assert "- main" in trigger
    assert "feat/e2e-powerplatform-oidc-20260917" not in trigger

    for path in (
        "scripts/integration_excel_sql_sharepoint_dataverse.py",
        "scripts/integration_excel_sql_sharepoint_oidc_discovery.py",
        "scripts/integration_excel_sql_sharepoint_e2e_oidc.py",
        "scripts/integration_excel_sql_sharepoint_e2e_cleanup_oidc.py",
    ):
        assert path in trigger


def test_oidc_automatico_nao_depende_de_device_code():
    text = OIDC_WORKFLOW.read_text(encoding="utf-8").lower()
    assert "msal_device_code" not in text
    assert "device code" not in text
    assert "device_code" not in text


def test_legado_device_code_fica_somente_manual():
    text = LEGACY_WORKFLOW.read_text(encoding="utf-8")
    trigger = _workflow_trigger_block(text)

    assert "workflow_dispatch:" in trigger
    assert "push:" not in trigger
    assert "pull_request:" not in trigger
    assert "msal_device_code" in text
