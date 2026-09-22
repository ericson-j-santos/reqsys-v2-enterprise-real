from pathlib import Path


def test_implementation_note_preserves_production_guardrails() -> None:
    note = Path("docs/changelog/fly-automatic-promotion-implementation.md").read_text(
        encoding="utf-8"
    )
    assert "BACEN Production Hard Gate" in note
    assert "nenhum valor de secret" in note
    assert "rollback produtivo" in note
    assert "production_touched=false" in note
