from pathlib import Path


WORKFLOW = Path('.github/workflows/pc24x7-teams-ephemeral-e2e.yml')


def test_workflow_uses_development_environment_without_azure_oidc() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'environment: development' in text
    assert 'COFRE_ADMIN_JWT: ${{ secrets.COFRE_ADMIN_JWT }}' in text
    assert 'Validar credencial administrativa disponível' not in text
    assert 'autenticação administrativa efêmera' in text
    assert 'id-token: write' not in text
    assert 'azure/login' not in text
    assert 'CCP_AZURE_CLIENT_ID' not in text
    assert 'VAULT_API_TOKEN' not in text
    assert 'REQSYS_KEY_VAULT_NAME' not in text


def test_workflow_is_dev_only_and_does_not_execute_e2e_in_pr() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'https://reqsys-api-dev.fly.dev' not in text
    assert 'reqsys-api-stg' not in text
    assert 'https://reqsys-api.fly.dev' not in text
    assert 'workflow_run:' not in text
    assert 'Fly DEV Fast Deploy' not in text
    assert "if: github.event_name == 'workflow_dispatch'" in text
    assert "github.event_name == 'push'" not in text
    assert 'pull_request:' in text
    assert 'resolve_pc24x7_dev_locator.mjs --self-test' in text
    assert '--output artifacts/pc24x7-teams-ephemeral-e2e/signed-locator.json' in text
    assert 'steps.locator.outputs.base_url' in text
    assert 'steps.locator.outputs.api_base_url' in text
    assert '/api/runtime/build-info' in text
    assert 'pc24x7_runtime_sha_mismatch' in text
    assert 'EXPECTED_SHA: ${{ github.sha }}' in text

def test_workflow_runs_focused_tests_and_publishes_only_sanitized_artifact() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'tests/test_pc24x7_teams_ephemeral_e2e.py' in text
    assert 'tests/test_pc24x7_teams_queue.py' in text
    assert 'scripts/pc24x7_teams_ephemeral_e2e.py' in text
    assert 'artifacts/pc24x7-teams-ephemeral-e2e/evidence.json' in text
    assert 'actions/upload-artifact@v4' in text
