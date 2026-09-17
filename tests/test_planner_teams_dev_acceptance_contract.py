from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "planner_teams_dev_acceptance_v2.mjs"


def test_acceptance_keeps_flows_started_after_proof() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "flowAction(environmentId, flowId, 'stop'" not in source
    assert "flow_final_state" in source
    assert "postconditions" in source
    assert "started_confirmed" in source


def test_acceptance_preserves_positive_and_negative_controls() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "REQSYS-E2E-NOTIFY-FILTER-" in source
    assert "REQSYS-NOTIFY-FILTER-NORMAL-" in source
    assert "expected_teams: 'skipped'" in source
    assert "expected_teams: 'succeeded'" in source


def test_acceptance_persists_sanitized_auth_failure_diagnostics() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "function classifyFailure(error)" in source
    assert "failure_stage: succeeded ? null" in source
    assert "msal_refresh_token_ausente" in source
    assert "msal_refresh_token_expirado" in source
    assert "device_code_expirado_sem_autorizacao" in source
    assert "oauth_token_exchange_failed" in source
    assert "acceptance_failed_see_runtime_log" not in source

def test_acceptance_persists_sanitized_post_auth_failure_diagnostics() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for code in ['power_platform_connections_failed', 'planner_connection_ambiguous', 'teams_connection_ambiguous', 'planner_connection_not_found', 'teams_connection_not_found', 'provisioning_deploy_request_failed', 'provisioning_not_implanted', 'flow_state_query_failed', 'flow_start_failed', 'flow_not_started', 'planner_task_create_failed', 'flow_runs_query_failed', 'created_flow_runs_insufficient']:
        assert code in source

