from pathlib import Path


def test_evidence_map_covers_all_promotion_inputs() -> None:
    content = Path("docs/operations/fly-automatic-promotion-evidence-map.md").read_text(
        encoding="utf-8"
    )
    for expected in (
        "flyctl status --json",
        "flyctl config show",
        "flyctl secrets list --json",
        "flyctl releases --json",
        "flyctl checks list --json",
        "validate_public_runtime.py",
        "validate_publication_sync.py",
        "validar_login_multi_ambiente.py",
        "BACEN Production Hard Gate",
    ):
        assert expected in content
