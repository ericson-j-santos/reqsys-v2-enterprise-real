from pathlib import Path


FILES = [
    Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission_v2.py'),
    Path('.github/workflows/pc24x7-teams-oidc-environment-bootstrap.yml'),
]


def test_codigo_nao_concede_application_readwrite_all() -> None:
    script = FILES[0].read_text(encoding='utf-8')
    workflow = FILES[1].read_text(encoding='utf-8')
    assert 'application_readwrite_all_granted": True' not in script
    assert 'Application.ReadWrite.All' not in workflow
    assert 'OWNED_BY_APP_ROLE_ID' in script
