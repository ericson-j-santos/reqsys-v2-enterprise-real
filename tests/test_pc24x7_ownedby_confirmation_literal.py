from pathlib import Path


def test_confirmacao_literal_exigida() -> None:
    text = Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py').read_text(encoding='utf-8')
    assert 'TEMP-OWNEDBY-PC24X7-TEAMS-DEV' in text
    assert 'Confirmação inválida' in text
