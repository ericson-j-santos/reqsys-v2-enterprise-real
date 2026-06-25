"""Testes do contrato governado de telemetria OBS-P0.1."""
from datetime import UTC, datetime

from app.core.telemetry_contract import (
    build_evidence_index,
    calculate_drift_analytics,
    sample_valid_event,
    validate_telemetry_event,
)


def test_sample_valid_event_obedece_contrato():
    result = validate_telemetry_event(sample_valid_event())

    assert result.valid is True
    assert result.errors == ()


def test_evento_sem_correlation_id_e_bloqueado():
    event = sample_valid_event()
    event.pop("correlation_id")

    result = validate_telemetry_event(event)

    assert result.valid is False
    assert "missing required field: correlation_id" in result.errors


def test_evento_com_status_invalido_e_bloqueado():
    event = sample_valid_event()
    event["status"] = "ok"

    result = validate_telemetry_event(event)

    assert result.valid is False
    assert "invalid status: ok" in result.errors


def test_timestamp_sem_timezone_e_bloqueado():
    event = sample_valid_event()
    event["timestamp"] = datetime.now().isoformat()

    result = validate_telemetry_event(event)

    assert result.valid is False
    assert "invalid timestamp: timezone is required" in result.errors


def test_timestamp_utc_com_timezone_e_aceito():
    event = sample_valid_event()
    event["timestamp"] = datetime.now(UTC).isoformat()

    result = validate_telemetry_event(event)

    assert result.valid is True


def test_metadata_com_chave_sensivel_e_bloqueado():
    event = sample_valid_event()
    event["metadata"] = {"token": "nao-deve-aparecer"}

    result = validate_telemetry_event(event)

    assert result.valid is False
    assert "forbidden sensitive keys in metadata: token" in result.errors


def test_evidence_index_contem_kpis_obrigatorios():
    evidence = build_evidence_index()

    assert evidence["domain"] == "REQSYS#003"
    assert evidence["target_branch"] == "ai/observability"
    assert evidence["coverage"]["telemetry_contract"] is True
    assert evidence["coverage"]["ci_contract_gate"] is True
    assert evidence["kpis"]["telemetry_contract_coverage_pct"] == 100


def test_drift_analytics_classifica_eventos_invalidos():
    valid_event = sample_valid_event()
    invalid_event = sample_valid_event()
    invalid_event["event_type"] = "unknown"

    drift = calculate_drift_analytics([valid_event, invalid_event])

    assert drift["total_events"] == 2
    assert drift["valid_events"] == 1
    assert drift["invalid_events"] == 1
    assert drift["invalid_pct"] == 50.0
    assert drift["drift_level"] == "critical"
