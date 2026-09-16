from pathlib import Path


def test_script_revoga_em_finally() -> None:
    text = Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py').read_text(encoding='utf-8')
    assert 'finally:' in text
    assert '_revoke_assignment' in text
    assert 'Revogação temporária não foi comprovada' in text
