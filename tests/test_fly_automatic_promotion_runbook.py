from pathlib import Path


def test_runbook_exposes_artifact_driven_diagnostics() -> None:
    runbook = Path("docs/runbooks/fly-automatic-promotion.md").read_text(encoding="utf-8")
    assert "decision.json" in runbook
    assert "blocking_issues" in runbook
    assert "Valores, tokens e senhas não são persistidos" in runbook
    assert "Produção não possui bypass" in runbook
