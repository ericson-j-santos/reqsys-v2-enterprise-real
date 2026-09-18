from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / ".github/workflows/planner-teams-notify-dev-acceptance.yml"
RUNTIME = ROOT / ".github/workflows/runtime-e2e-continuous.yml"


def test_acceptance_reuses_oidc_runtime_without_device_code() -> None:
    source = ACCEPTANCE.read_text(encoding="utf-8")
    assert "uses: ./.github/workflows/runtime-e2e-continuous.yml" in source
    assert "secrets: inherit" in source
    assert "id-token: write" in source
    assert "msal_device_code" not in source.lower()
    assert "device_code" not in source.lower()
    assert "WSJF_MSAL_STORAGE_STATE_B64" not in source
    assert "POWER_PLATFORM_CLIENT_SECRET" not in source


def test_runtime_is_reusable_and_oidc_only() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    assert "workflow_call:" in source
    assert "azure/login@v2" in source
    assert "id-token: write" in source
    assert "POWER_PLATFORM_GRAPH_ACCESS_TOKEN" in source
    assert "planner_teams_runtime_e2e.mjs" in source
    assert "planner_teams_flow_state_oidc.py" in source
    assert "PLANNER_TEAMS_DATAVERSE_URL" in source
    assert "POWER_PLATFORM_DATAVERSE_ACCESS_TOKEN" in source
    assert "msal_device_code" not in source.lower()
    assert "device_code" not in source.lower()
