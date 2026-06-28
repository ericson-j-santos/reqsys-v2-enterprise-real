from pathlib import Path


def test_strategic_governance_dashboard_renders_executive_trend_history() -> None:
    html = Path('docs/ops-dashboard/strategic-governance.html').read_text(encoding='utf-8')

    assert 'Executive Trend History' in html
    assert './data/executive-trend-history.json' in html
    assert 'trend-executive' in html
    assert 'trend-decay' in html
    assert 'trend-freeze' in html
    assert 'freeze_expansion' in html
    assert 'recommendation-only' in html


def test_strategic_governance_dashboard_keeps_static_guardrails() -> None:
    html = Path('docs/ops-dashboard/strategic-governance.html').read_text(encoding='utf-8')

    assert "cache: 'no-store'" in html
    assert 'runtime-executive-index.json' in html
    assert 'strategic-governance-index.json' in html
    assert 'não substitui CI' in html
