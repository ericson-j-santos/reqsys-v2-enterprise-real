from pathlib import Path


def test_script_valida_tenant_antes_da_mutacao() -> None:
    text = Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py').read_text(encoding='utf-8')
    assert 'Tenant ativo diverge do tenant esperado.' in text
    assert text.index('Tenant ativo diverge do tenant esperado.') < text.index('_grant_ownedby(')
