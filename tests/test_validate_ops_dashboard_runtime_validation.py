from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_validate_ops_dashboard_runtime_validation_passes_on_repo_artifacts() -> None:
    from scripts.validate_ops_dashboard_runtime_validation import (
        validate_executive_brief,
        validate_runtime_executive_index,
        validate_snapshot_when_present,
    )

    validate_executive_brief()
    validate_runtime_executive_index()
    validate_snapshot_when_present()


def test_operational_navigation_index_links_executive_brief() -> None:
    import json

    payload = json.loads((ROOT / "docs/ops-dashboard/operational-navigation-index.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in payload["links"]}
    assert "executive_brief_dashboard" in by_id
    assert by_id["executive_brief_dashboard"]["href"] == "./data/executive-brief.json"
