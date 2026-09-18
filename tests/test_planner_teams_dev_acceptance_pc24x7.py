from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/planner-teams-notify-dev-acceptance.yml"


def test_acceptance_uses_pc24x7_runtime_fail_closed() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "API_URL: ${{ vars.PC24X7_DEV_BASE_URL }}" in source
    assert "https://reqsys-api-dev.fly.dev" not in source
    assert "PC24X7_DEV_BASE_URL não configurada" in source
    assert "PC24X7_DEV_BASE_URL deve usar HTTPS" in source
    assert "Planner Teams DEV Acceptance não pode usar Fly.io" in source
    assert '${API_URL%/}/api/runtime/health' in source


def test_acceptance_renews_device_code_without_restarting_run() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/msal_device_code_complete.mjs" in source
    assert "DEVICE_CODE_TOTAL_WAIT_MINUTES: '50'" in source
    assert "Aguardar autorização Microsoft com renovação automática" in source
    assert "Se expirar, o job renovará automaticamente" in source
    assert "timeout-minutes: 70" in source


def test_acceptance_restores_and_persists_delegated_session_in_key_vault() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "id-token: write" in source
    assert "azure/login@v2" in source
    assert "REQSYS_KEY_VAULT_NAME: ${{ vars.REQSYS_KEY_VAULT_NAME }}" in source
    assert "planner_teams_delegated_session_store.py load" in source
    assert "planner_teams_delegated_session_store.py persist" in source
    assert "MSAL_BOOTSTRAP_CLIENT_ID" not in source  # produzido pelo loader, nunca hardcoded
    assert "base64 --decode" not in source
    assert "DELEGATED_SESSION_EVIDENCE_PATH" in source


def test_legacy_session_is_only_transitional_input() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "WSJF_MSAL_STORAGE_STATE_B64: ${{ secrets.WSJF_MSAL_STORAGE_STATE_B64 }}" in source
    restore_block = source.split("- name: Restaurar sessão Microsoft do Azure Key Vault", 1)[1].split(
        "- name: Preparar autorização Microsoft", 1
    )[0]
    assert "WSJF_MSAL_STORAGE_STATE_B64" not in restore_block
    assert "base64" not in restore_block
