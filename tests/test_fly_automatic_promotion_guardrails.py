from pathlib import Path


def test_guardrails_preserve_sequence_bacen_and_secret_safety() -> None:
    content = Path("docs/governance/fly-automatic-promotion-guardrails.md").read_text(
        encoding="utf-8"
    )
    assert "DEV precisa estar validado antes de STG" in content
    assert "STG precisa estar validado antes de PROD" in content
    assert "BACEN Production Hard Gate" in content
    assert "Valores de secrets nunca são persistidos" in content
