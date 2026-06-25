"""Contrato governado de telemetria do ReqSys.

Este módulo é intencionalmente livre de dependências externas para permitir
validação rápida em CI, scripts locais e futuros coletores OpenTelemetry.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any

REQUIRED_EVENT_FIELDS = (
    "event_name",
    "event_type",
    "module",
    "action",
    "status",
    "severity",
    "correlation_id",
    "trace_id",
    "session_id",
    "environment",
    "timestamp",
)

OPTIONAL_EVENT_FIELDS = (
    "duration_ms",
    "http_status",
    "resource_id",
    "resource_type",
    "actor_type",
    "evidence_id",
    "evidence_url",
    "drift_type",
    "metric_name",
    "metric_value",
    "tags",
    "metadata",
)

ALLOWED_EVENT_TYPES = {
    "trace",
    "log",
    "metric",
    "evidence",
    "drift",
    "security",
    "runtime",
}

ALLOWED_STATUSES = {
    "success",
    "warning",
    "error",
    "skipped",
}

ALLOWED_SEVERITIES = {
    "debug",
    "info",
    "warning",
    "error",
    "critical",
}

ALLOWED_ENVIRONMENTS = {
    "local",
    "dev",
    "test",
    "staging",
    "production",
}

_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{2,120}$")
_TRACE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.:-]{8,128}$")
_FORBIDDEN_METADATA_KEYS = {
    "senha",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "secret",
    "cpf",
    "cnpj",
    "connection_string",
}


@dataclass(frozen=True)
class TelemetryValidationResult:
    """Resultado normalizado da validação do contrato."""

    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def utc_now_iso() -> str:
    """Retorna timestamp ISO-8601 em UTC para eventos de telemetria."""
    return datetime.now(UTC).isoformat()


def build_telemetry_event(
    *,
    event_name: str,
    event_type: str,
    module: str,
    action: str,
    status: str,
    severity: str,
    correlation_id: str,
    trace_id: str,
    session_id: str,
    environment: str,
    timestamp: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Monta um evento compatível com o contrato governado."""
    event = {
        "event_name": event_name,
        "event_type": event_type,
        "module": module,
        "action": action,
        "status": status,
        "severity": severity,
        "correlation_id": correlation_id,
        "trace_id": trace_id,
        "session_id": session_id,
        "environment": environment,
        "timestamp": timestamp or utc_now_iso(),
    }
    for key, value in extra.items():
        if value is not None:
            event[key] = value
    return event


def validate_telemetry_event(event: dict[str, Any]) -> TelemetryValidationResult:
    """Valida um evento individual de telemetria.

    O contrato bloqueia campos obrigatórios ausentes, enumerações inválidas,
    timestamps sem timezone e metadados com chaves sensíveis.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(event, dict):
        return TelemetryValidationResult(False, ("event must be a dict",), ())

    for field in REQUIRED_EVENT_FIELDS:
        if field not in event:
            errors.append(f"missing required field: {field}")
        elif event[field] in (None, ""):
            errors.append(f"empty required field: {field}")

    if errors:
        return TelemetryValidationResult(False, tuple(errors), tuple(warnings))

    _validate_token_field(event, "event_name", errors)
    _validate_token_field(event, "module", errors)
    _validate_token_field(event, "action", errors)

    if event["event_type"] not in ALLOWED_EVENT_TYPES:
        errors.append(f"invalid event_type: {event['event_type']}")

    if event["status"] not in ALLOWED_STATUSES:
        errors.append(f"invalid status: {event['status']}")

    if event["severity"] not in ALLOWED_SEVERITIES:
        errors.append(f"invalid severity: {event['severity']}")

    if event["environment"] not in ALLOWED_ENVIRONMENTS:
        errors.append(f"invalid environment: {event['environment']}")

    for field in ("correlation_id", "trace_id", "session_id"):
        value = str(event[field])
        if not _TRACE_ID_PATTERN.fullmatch(value):
            errors.append(f"invalid identifier format: {field}")

    _validate_timestamp(event["timestamp"], errors)
    _validate_numeric_optional(event, "duration_ms", min_value=0, errors=errors)
    _validate_numeric_optional(event, "http_status", min_value=100, max_value=599, errors=errors)
    _validate_numeric_optional(event, "metric_value", errors=errors)
    _validate_metadata(event, errors, warnings)

    unknown_fields = sorted(set(event) - set(REQUIRED_EVENT_FIELDS) - set(OPTIONAL_EVENT_FIELDS))
    if unknown_fields:
        warnings.append(f"unknown fields ignored by contract: {', '.join(unknown_fields)}")

    return TelemetryValidationResult(not errors, tuple(errors), tuple(warnings))


def sample_valid_event() -> dict[str, Any]:
    """Evento mínimo válido usado por CI e documentação viva."""
    return build_telemetry_event(
        event_name="runtime.health.snapshot",
        event_type="runtime",
        module="observability",
        action="snapshot",
        status="success",
        severity="info",
        correlation_id="corr-reqsys-observability-p0-1",
        trace_id="trace-reqsys-observability-p0-1",
        session_id="session-reqsys-observability-p0-1",
        environment="test",
        duration_ms=12,
        metric_name="runtime_visibility_score",
        metric_value=0.59,
        tags={"domain": "telemetry_analytics", "increment": "OBS-P0.1"},
    )


def build_evidence_index() -> dict[str, Any]:
    """Índice determinístico de evidências da frente de observabilidade."""
    return {
        "domain": "REQSYS#003",
        "name": "IA_OBSERVABILIDADE_TELEMETRIA_ANALYTICS",
        "increment": "OBS-P0.1",
        "status": "implemented_pending_ci",
        "target_branch": "ai/observability",
        "coverage": {
            "telemetry_contract": True,
            "runtime_health": True,
            "evidence_index": True,
            "drift_analytics": True,
            "ci_contract_gate": True,
            "dashboard_runtime_graph": False,
        },
        "kpis": {
            "telemetry_contract_coverage_pct": 100,
            "runtime_visibility_pct": 65,
            "alert_coverage_pct": 25,
            "trace_usefulness_pct": 60,
            "evidence_traceability_pct": 70,
        },
        "required_fields": list(REQUIRED_EVENT_FIELDS),
        "allowed_event_types": sorted(ALLOWED_EVENT_TYPES),
        "generated_at": utc_now_iso(),
    }


def calculate_drift_analytics(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Calcula drift básico de conformidade dos eventos recebidos."""
    total = len(events)
    invalid = 0
    invalid_by_reason: dict[str, int] = {}

    for event in events:
        result = validate_telemetry_event(event)
        if not result.valid:
            invalid += 1
            for error in result.errors:
                invalid_by_reason[error] = invalid_by_reason.get(error, 0) + 1

    valid = total - invalid
    invalid_pct = round((invalid / total) * 100, 2) if total else 0.0
    drift_level = "none"
    if invalid_pct > 20:
        drift_level = "critical"
    elif invalid_pct > 10:
        drift_level = "high"
    elif invalid_pct > 0:
        drift_level = "medium"

    return {
        "total_events": total,
        "valid_events": valid,
        "invalid_events": invalid,
        "invalid_pct": invalid_pct,
        "drift_level": drift_level,
        "invalid_by_reason": invalid_by_reason,
    }


def _validate_token_field(event: dict[str, Any], field: str, errors: list[str]) -> None:
    value = str(event[field])
    if not _TOKEN_PATTERN.fullmatch(value):
        errors.append(f"invalid token format: {field}")


def _validate_timestamp(value: Any, errors: list[str]) -> None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        errors.append("invalid timestamp: expected ISO-8601")
        return

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append("invalid timestamp: timezone is required")


def _validate_numeric_optional(
    event: dict[str, Any],
    field: str,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
    errors: list[str],
) -> None:
    if field not in event:
        return

    value = event[field]
    if not isinstance(value, (int, float)):
        errors.append(f"invalid numeric field: {field}")
        return

    if min_value is not None and value < min_value:
        errors.append(f"{field} below minimum: {min_value}")

    if max_value is not None and value > max_value:
        errors.append(f"{field} above maximum: {max_value}")


def _validate_metadata(
    event: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    for container_field in ("metadata", "tags"):
        if container_field not in event:
            continue

        container = event[container_field]
        if not isinstance(container, dict):
            errors.append(f"invalid {container_field}: expected dict")
            continue

        forbidden = sorted(
            key for key in container
            if str(key).lower() in _FORBIDDEN_METADATA_KEYS
        )
        if forbidden:
            errors.append(
                f"forbidden sensitive keys in {container_field}: {', '.join(forbidden)}"
            )

        if len(container) > 30:
            warnings.append(f"{container_field} has more than 30 entries")
