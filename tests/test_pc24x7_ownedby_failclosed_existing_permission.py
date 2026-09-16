from pathlib import Path


def test_script_bloqueia_ownedby_preexistente() -> None:
    text = Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py').read_text(encoding='utf-8')
    assert 'OWNEDBY_ALREADY_PRESENT' in text
    assert 'preexisting_permission_must_not_be_revoked_implicitly' in text
