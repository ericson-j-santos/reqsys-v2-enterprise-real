"""Endpoints de observabilidade, telemetria e analytics do ReqSys."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body

from app.core.envelope import ok
from app.core.telemetry_contract import (
    build_evidence_index,
    calculate_drift_analytics,
    sample_valid_event,
    validate_telemetry_event,
)

router = APIRouter(prefix="/v1/telemetry-analytics", tags=["Telemetry Analytics"])


@router.get("/contract")
def telemetry_contract_snapshot():
    """Retorna contrato governado e exemplo mínimo válido."""
    sample = sample_valid_event()
    validation = validate_telemetry_event(sample)

    return ok({
        "contract_version": "OBS-P0.1",
        "status": "implemented_pending_ci",
        "valid_sample": validation.to_dict(),
        "sample_event": sample,
        "policy": {
            "pii_policy": "metadata e tags nao podem conter chaves sensiveis",
            "required_correlation": True,
            "required_trace": True,
            "timestamp_timezone_required": True,
            "invalid_event_blocks_ci": True,
        },
    })


@router.get("/evidence-index")
def telemetry_evidence_index():
    """Retorna índice de evidências rastreável para dashboards e auditoria."""
    return ok(build_evidence_index())


@router.get("/runtime-health")
def telemetry_runtime_health():
    """Retorna snapshot executivo da visibilidade operacional da frente."""
    evidence = build_evidence_index()
    kpis = evidence["kpis"]

    status = "warning"
    if (
        kpis["telemetry_contract_coverage_pct"] >= 100
        and kpis["evidence_traceability_pct"] >= 70
        and evidence["coverage"]["ci_contract_gate"]
    ):
        status = "operational_pending_dashboard"

    return ok({
        "timestamp": datetime.now(UTC).isoformat(),
        "domain": evidence["domain"],
        "branch": evidence["target_branch"],
        "status": status,
        "maturity": {
            "current_level": "enterprise_initial",
            "target_level": "gold_standard",
            "evidenced_pct": 59,
            "technical_progress_pct": 65,
            "operational_progress_pct": 50,
            "confidence_pct": 72,
        },
        "kpis": kpis,
        "known_gaps": [
            {
                "id": "OBS-GAP-001",
                "name": "dashboard_runtime_graph",
                "severity": "medium",
                "status": "backlog_next_increment",
            },
            {
                "id": "OBS-GAP-002",
                "name": "alert_coverage_full",
                "severity": "medium",
                "status": "partial",
            },
        ],
    })


@router.post("/drift")
def telemetry_drift_analytics(events: list[dict[str, Any]] = Body(default_factory=list)):
    """Calcula drift de conformidade para lote de eventos de telemetria."""
    return ok(calculate_drift_analytics(events))
