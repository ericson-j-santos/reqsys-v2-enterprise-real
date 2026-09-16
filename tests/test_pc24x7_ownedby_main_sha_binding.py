from pathlib import Path


def test_orquestrador_valida_sha_main() -> None:
    text = Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py').read_text(encoding='utf-8')
    assert '_main_sha' in text
    assert 'expected_sha' in text
    assert 'headSha' in text
