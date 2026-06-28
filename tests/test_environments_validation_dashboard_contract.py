from pathlib import Path


def test_environments_validation_dashboard_loads_artifact() -> None:
    html = Path('docs/ops-dashboard/environments-validation.html').read_text(encoding='utf-8')

    assert 'Environments Validation' in html
    assert './data/environments-validation.json' in html
    assert 'environment-cards' in html
    assert 'environment-table' in html
    assert "cache: 'no-store'" in html
