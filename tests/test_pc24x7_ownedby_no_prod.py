from pathlib import Path


def test_automacao_dev_only() -> None:
    files = [
        Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py'),
        Path('.github/workflows/pc24x7-teams-oidc-environment-bootstrap.yml'),
    ]
    text = '\n'.join(path.read_text(encoding='utf-8') for path in files)
    assert 'reqsys-api-stg' not in text
    assert 'reqsys-api-prod' not in text
