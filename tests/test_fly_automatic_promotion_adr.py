from pathlib import Path


def test_adr_keeps_prod_governed_and_rollback_separate() -> None:
    adr = Path("docs/decisions/ADR-automatic-fly-environment-promotion.md").read_text(
        encoding="utf-8"
    )
    assert "BACEN Production Hard Gate" in adr
    assert "rollback continua separado" in adr
    assert "SHA atual da `main`" in adr
