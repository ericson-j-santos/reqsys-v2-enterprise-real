from pathlib import Path


def test_workflow_nao_toca_runtime_ou_deploy() -> None:
    text = Path('.github/workflows/pc24x7-teams-oidc-environment-bootstrap.yml').read_text(encoding='utf-8')
    assert 'flyctl' not in text
    assert 'deploy' not in text.lower()
    assert 'bootstrap_pc24x7_teams_oidc_environment.py' in text
