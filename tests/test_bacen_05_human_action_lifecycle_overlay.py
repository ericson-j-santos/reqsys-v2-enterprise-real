from pathlib import Path

import yaml

from scripts.generate_bacen_human_actions_backlog import build_backlog


def write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def matrix_payload() -> dict:
    return {
        "controls": [
            {
                "id": "BACEN-05",
                "title": "Gestão de nuvem e terceiros",
                "domain": "third_party",
                "status": "partial",
                "criticality": "high",
                "owner": "AI_GOVERNOR",
                "evidence": "artifacts/bacen/bacen-05-consolidated-readiness.json",
                "next_stage": "ingest_validated_dpa_references_and_complete_formal_legal_signoff",
                "production_touched": False,
            }
        ]
    }


def lifecycle_payload(stage: str) -> dict:
    return {
        "control_id": "BACEN-05",
        "lifecycle_stage": stage,
        "institutional_governance_status": "deferred_until_institutionalization",
        "institutional_governance_gate_stage": "PRODUCTION",
        "production_touched": False,
        "next_stage": "continue_technical_vendor_evidence_until_production_gate",
    }


def test_development_overlay_defers_current_human_action(tmp_path: Path) -> None:
    matrix = tmp_path / "BACEN-CONTROL-MATRIX.yaml"
    lifecycle = tmp_path / "BACEN-05-LIFECYCLE.yaml"
    write_yaml(matrix, matrix_payload())
    write_yaml(lifecycle, lifecycle_payload("DEVELOPMENT"))

    report = build_backlog(matrix)

    assert report["items"] == []
    assert [item["control_id"] for item in report["deferred_items"]] == ["BACEN-05"]
    assert report["deferred_items"][0]["lifecycle_stage"] == "DEVELOPMENT"
    assert report["deferred_items"][0]["human_action_required_now"] is False
    assert report["deferred_items"][0]["required_action"] == (
        "continue_technical_vendor_evidence_until_production_gate"
    )
    assert report["summary"]["pending_controls"] == 0
    assert report["summary"]["deferred_controls"] == 1
    assert report["human_action_required"] is False
    assert report["lifecycle_contracts"][0]["control_id"] == "BACEN-05"
    assert len(report["lifecycle_contracts"][0]["sha256"]) == 64


def test_production_overlay_reactivates_human_action(tmp_path: Path) -> None:
    matrix = tmp_path / "BACEN-CONTROL-MATRIX.yaml"
    lifecycle = tmp_path / "BACEN-05-LIFECYCLE.yaml"
    write_yaml(matrix, matrix_payload())
    write_yaml(lifecycle, lifecycle_payload("PRODUCTION"))

    report = build_backlog(matrix)

    assert [item["control_id"] for item in report["items"]] == ["BACEN-05"]
    assert report["deferred_items"] == []
    assert report["items"][0]["human_action_required_now"] is True
    assert report["items"][0]["institutional_gate_stage"] == "PRODUCTION"
    assert report["human_action_required"] is True
