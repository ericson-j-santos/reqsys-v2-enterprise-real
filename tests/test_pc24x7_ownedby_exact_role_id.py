from pathlib import Path


def test_role_id_ownedby_exato() -> None:
    text = Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py').read_text(encoding='utf-8')
    assert '18a4783c-866b-4cc7-a460-3d5e5662c884' in text
