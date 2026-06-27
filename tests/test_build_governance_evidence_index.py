from __future__ import annotations

import json
from pathlib import Path

from scripts.build_governance_evidence_index import build_payload, write_payload


def test_build_payload_has_dashboard_contract() -> None:
    payload = build_payload()

    assert payload["schema_version"] == "1.0.0"
    assert payload["overall_status"] in {"green", "yellow"}
    assert payload["governance_evidence_score"] >= 80
    assert payload["summary"]["implemented_capabilities"] == payload["summary"]["total_capabilities"]
    assert payload["runtime_dashboard_contract"]["card_fields"]


def test_build_payload_contains_core_evidence_items() -> None:
    payload = build_payload()
    evidence_ids = {item["id"] for item in payload["evidence"]}

    assert "conflict_prediction" in evidence_ids
    assert "runtime_merge_queue" in evidence_ids
    assert "preview_environment" in evidence_ids
    assert "governed_pr_automation" in evidence_ids


def test_write_payload_creates_valid_json(tmp_path: Path) -> None:
    output = tmp_path / "governance-evidence-index.json"
    payload = write_payload(str(output))
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert loaded["repo"] == payload["repo"]
    assert loaded["evidence"]
