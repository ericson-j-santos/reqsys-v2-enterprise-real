from pathlib import Path

WORKFLOW = Path('.github/workflows/pc24x7-teams-token-bootstrap.yml')


def test_human_credential_job_is_manual_and_isolated_from_scheduled_bootstrap() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'workflow_dispatch:' in text
    assert 'pull_request:' in text
    human_job = text.split('  human-admin-jwt-dev:', 1)[1].split(
        '\n  reconcile-runtime-dev:', 1
    )[0]
    assert "if: github.event_name == 'workflow_dispatch' && inputs.operation != 'bootstrap'" in human_job
    assert 'runs-on: [self-hosted, Windows, X64, reqsys-dev, reqsys-dev-runtime-v1]' in human_job
    assert 'environment: development' in human_job
    assert 'cancel-in-progress: false' in text
    schedule = text.split('  schedule:', 1)[1].split('  workflow_dispatch:', 1)[0]
    assert 'credential-renew' not in schedule


def test_workflow_keeps_mfa_human_and_publishes_only_sanitized_status() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    human_job = text.split('  human-admin-jwt-dev:', 1)[1].split(
        '\n  reconcile-runtime-dev:', 1
    )[0]

    assert "inputs.operation == 'credential-renew'" in human_job
    assert 'device-login' in human_job
    assert '--environment dev' in human_job
    assert '--require-valid' in human_job
    assert 'local-status' in human_job
    assert 'signed-locator.json' in human_job
    assert 'COFRE_ADMIN_JWT' not in human_job
    assert 'VAULT_API_TOKEN' not in human_job
    assert 'secrets.' not in human_job
    assert 'artifacts/cofre-human-admin-jwt-renewal/' in human_job


def test_workflow_pins_external_actions_and_runs_focused_contract_tests() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' in text
    assert 'actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97' in text
    assert 'actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a' in text
    assert 'tests/test_cofre_human_token_device_login.py' in text
    assert 'tests/test_cofre_human_token_renewal_workflow.py' in text


def test_non_bootstrap_manual_operation_skips_reconcile_and_s2s_mutation() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    guarded = "github.event_name != 'workflow_dispatch' || inputs.operation == 'bootstrap'"

    for job_name in ('reconcile-runtime-dev', 'bootstrap-token-dev', 'bootstrap-dev'):
        job = text.split(f'  {job_name}:', 1)[1]
        assert guarded in job.split('\n', 3)[1]
