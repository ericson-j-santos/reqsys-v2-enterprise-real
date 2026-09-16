from pathlib import Path


def test_automacao_nao_contem_fallback_para_application_readwrite_all() -> None:
    script = Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py').read_text(encoding='utf-8')
    workflow = Path('.github/workflows/pc24x7-teams-oidc-environment-bootstrap.yml').read_text(encoding='utf-8')
    assert 'OWNED_BY_APP_ROLE_ID' in script
    assert 'application_readwrite_all_granted": True' not in script
    assert 'Application.ReadWrite.All' not in workflow
