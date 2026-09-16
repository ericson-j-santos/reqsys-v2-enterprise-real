from pathlib import Path


def test_resultado_declara_sem_all_sem_segredo() -> None:
    text = Path('scripts/bootstrap_pc24x7_teams_oidc_temporary_permission.py').read_text(encoding='utf-8')
    assert 'application_readwrite_all_granted' in text
    assert 'secret_value_exposed' in text
    assert 'rbac_changed' in text
