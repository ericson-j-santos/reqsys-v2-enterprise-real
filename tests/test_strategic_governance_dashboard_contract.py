from __future__ import annotations

from pathlib import Path


def test_strategic_governance_dashboard_contract_exists() -> None:
    html = Path("docs/ops-dashboard/strategic-governance.html").read_text(encoding="utf-8")

    assert "Strategic Governance Engine" in html
    assert "./data/strategic-governance-index.json" in html
    assert "priority-lanes" in html
    assert "next_bottleneck" in html
    assert "stabilizar_evidencias_antes_de_expandir" in html
    assert "priority_does_not_override_required_ci" not in html or "guardrails" in html


def test_strategic_governance_dashboard_is_report_only() -> None:
    html = Path("docs/ops-dashboard/strategic-governance.html").read_text(encoding="utf-8")

    assert "report-only" in html
    assert "não substitui CI" in html
    assert "fetch('./data/strategic-governance-index.json'" in html or "fetch(path" in html
    assert "no-store" in html
