from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pages-single-writer-guard.yml"


def test_pages_single_writer_counts_only_real_uses_lines() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "deploy_uses_pattern='^[[:space:]]*(-[[:space:]]*)?uses:"
        "[[:space:]]*actions/deploy-pages@'" in text
    )
    assert "grep -RIlE" in text
    assert (
        "grep -RIl --include='*.yml' --include='*.yaml' "
        "'actions/deploy-pages@'" not in text
    )


def test_pages_single_writer_counts_only_real_pages_write_permissions() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "'^[[:space:]]*pages:[[:space:]]*write([[:space:]]*#.*)?$'"
        in text
    )


def test_pages_single_writer_action_reference_is_immutable() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
        in text
    )
    assert "actions/checkout@v4" not in text
