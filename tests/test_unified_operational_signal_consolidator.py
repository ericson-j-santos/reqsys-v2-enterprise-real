from __future__ import annotations

import json
from pathlib import Path

from scripts.operational_alert_intelligence import classify_alert, build_payload
from scripts.unified_operational_event_bus import classify_event, build_payload as build_event_payload
from scripts.unified_operational_signal_consolidator import (
    build_evidence_gate_consolidated,
    build_snapshot,
    evaluate_alert_layer,
    evaluate_event_bus_layer,
    evaluate_mesh_layer,
)


def test_classify_alert_suppresses_informative_success() -> None:
    result = classify_alert("Operational Runtime Mesh Hub", "success")
    assert result["should_alert"] is False
    assert result["alert_type"] == "INFORMATIVE_EVIDENCE"


def test_classify_alert_high_on_failure() -> None:
    result = classify_alert("CI Enterprise Fast", "failure")
    assert result["alert_level"] == "HIGH"
    assert result["alert_type"] == "POTENTIAL_REGRESSION"


def test_classify_event_suppresses_informative_success() -> None:
    result = classify_event("Coordenador Status Consolidator", "success")
    assert result["should_emit"] is False
    assert result["event_class"] == "INFORMATIVE_EVIDENCE"


def test_classify_event_incident_on_failure() -> None:
    result = classify_event("CI Enterprise Fast", "failure")
    assert result["should_emit"] is True
    assert result["event_class"] == "OPERATIONAL_INCIDENT"
    assert result["routing_key"] == "ops.incident"


def test_mesh_layer_from_payload() -> None:
    payload = {
        "mesh": {"event_mesh": "ACTIVE", "operational_risk": "LOW"},
        "alert_intelligence": {"alert_level": "INFO", "action_policy": "OBSERVE"},
    }
    layer = evaluate_mesh_layer(payload)
    assert layer["available"] is True
    assert layer["state"] == "green"


def test_build_snapshot_integrated_chain(tmp_path: Path) -> None:
    mesh_dir = tmp_path / "artifacts/operational-runtime-mesh-hub"
    mesh_dir.mkdir(parents=True)
    (mesh_dir / "operational-runtime-mesh-hub.json").write_text(
        json.dumps(
            {
                "mesh": {"event_mesh": "ACTIVE", "operational_risk": "LOW"},
                "alert_intelligence": {"alert_level": "INFO", "action_policy": "OBSERVE"},
            }
        ),
        encoding="utf-8",
    )

    alert_dir = tmp_path / "artifacts/operational-alert-intelligence"
    alert_dir.mkdir(parents=True)
    (alert_dir / "operational-alert-intelligence.json").write_text(
        json.dumps(
            {
                "should_alert": False,
                "alert_level": "INFO",
                "alert_type": "INFORMATIVE_EVIDENCE",
                "action_policy": "OBSERVE",
            }
        ),
        encoding="utf-8",
    )

    bus_dir = tmp_path / "artifacts/unified-operational-event-bus"
    bus_dir.mkdir(parents=True)
    (bus_dir / "unified-operational-event.json").write_text(
        json.dumps(
            {
                "should_emit": False,
                "event_class": "INFORMATIVE_EVIDENCE",
                "severity": "INFO",
                "routing_key": "ops.informative",
            }
        ),
        encoding="utf-8",
    )

    validation_dir = tmp_path / "artifacts/runtime-validation-consolidator"
    validation_dir.mkdir(parents=True)
    (validation_dir / "runtime-validation-snapshot.json").write_text(
        json.dumps(
            {
                "validation_score": 88,
                "overall_state": "green",
                "domains": {
                    "evidence_gate": {
                        "state": "green",
                        "score": 100,
                        "available": True,
                        "detail": "strict gate passed",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    snapshot = build_snapshot("owner/repo", "main", root=tmp_path)
    assert snapshot["mesh_integrated"] is True
    assert snapshot["evidence_gate_consolidated"]["consolidated"] is True
    assert snapshot["overall_state"] == "green"


def test_evidence_gate_consolidated_requires_two_layers() -> None:
    mesh = evaluate_mesh_layer(
        {"mesh": {"event_mesh": "ACTIVE", "operational_risk": "LOW"}, "alert_intelligence": {}}
    )
    alert = evaluate_alert_layer(None)
    event = evaluate_event_bus_layer(None)
    runtime = {
        "domains": {
            "evidence_gate": {
                "state": "green",
                "score": 100,
                "available": True,
                "detail": "ok",
            }
        }
    }
    result = build_evidence_gate_consolidated(runtime, mesh, alert, event)
    assert result["consolidated"] is True
    assert result["layers_available"] >= 2


def test_event_payload_contract_fields() -> None:
    payload = build_event_payload("manual", "success", commit="abc123")
    for field in ("generated_at", "source", "status", "confidence_level", "maturity_percent", "operational_risk"):
        assert field in payload
