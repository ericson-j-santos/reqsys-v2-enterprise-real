from pathlib import Path


def test_dod_keeps_ci_and_post_merge_evidence_pending_until_real() -> None:
    dod = Path("docs/checklists/fly-automatic-promotion-dod.md").read_text(encoding="utf-8")
    assert "[ ] CI completo verde" in dod
    assert "[ ] execução pós-merge real capturada" in dod
    assert "[x] BACEN Production Hard Gate" in dod
