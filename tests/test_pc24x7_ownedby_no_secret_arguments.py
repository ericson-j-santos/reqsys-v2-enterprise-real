from pathlib import Path


def test_orquestrador_nao_aceita_secret_password_token_flags() -> None:
    text = Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py').read_text(encoding='utf-8')
    lowered = text.lower()
    assert 'parser.add_argument("--password"' not in lowered
    assert 'parser.add_argument("--secret"' not in lowered
    assert 'parser.add_argument("--token"' not in lowered
