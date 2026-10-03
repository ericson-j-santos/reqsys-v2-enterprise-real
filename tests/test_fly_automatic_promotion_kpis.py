from pathlib import Path


def test_kpis_are_artifact_driven() -> None:
    content = Path("docs/metrics/fly-automatic-promotion-kpis.md").read_text(encoding="utf-8")
    assert "reports e artifacts" in content
    assert "sem inferir sucesso" in content
    assert "produção bloqueada pelo BACEN" in content
