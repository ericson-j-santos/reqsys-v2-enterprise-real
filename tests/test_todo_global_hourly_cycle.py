from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts import todo_global_hourly_cycle as cycle


def test_build_event_preserva_identidade_e_contrato(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    event = cycle.build_event(
        "123456",
        "2",
        datetime(2026, 9, 21, 18, 0, tzinfo=timezone.utc),
    )

    assert event["event_id"] == "todo-global-hourly-123456-2"
    assert event["correlation_id"] == event["event_id"]
    assert event["event_type"] == "todo.reconcile.requested"
    assert event["idempotency_key"] == cycle.IDEMPOTENCY_KEY
    assert len(event["idempotency_key"]) == 64
    assert event["todo"]["status"] == "EM ANDAMENTO"
    assert event["todo"]["evidence_url"].endswith("/actions/runs/123456")


def test_submit_valida_resposta_e_identidade(monkeypatch):
    event = cycle.build_event("123", "1")
    response = {
        "event_id": event["event_id"],
        "job_id": "job-1",
        "correlation_id": event["correlation_id"],
        "idempotency_key": event["idempotency_key"],
        "status_url": "/api/todo-events/" + event["event_id"],
        "duplicate_event": False,
    }
    monkeypatch.setattr(cycle, "request_json", lambda *args, **kwargs: (202, response))

    assert cycle.submit("https://runtime.example/api/todo-events", event, "") == response


def test_submit_falha_com_correlation_id_divergente(monkeypatch):
    event = cycle.build_event("123", "1")
    response = {
        "event_id": event["event_id"],
        "job_id": "job-1",
        "correlation_id": "correlation-divergente",
        "idempotency_key": event["idempotency_key"],
        "status_url": "/api/todo-events/" + event["event_id"],
    }
    monkeypatch.setattr(cycle, "request_json", lambda *args, **kwargs: (202, response))

    with pytest.raises(RuntimeError, match="correlation_id_divergente"):
        cycle.submit("https://runtime.example/api/todo-events", event, "")


def test_controle_negativo_exige_rejeicao(monkeypatch):
    monkeypatch.setattr(cycle, "request_json", lambda *args, **kwargs: (202, {}))

    with pytest.raises(RuntimeError, match="controle_negativo_nao_rejeitado"):
        cycle.assert_negative_control("https://runtime.example/api/todo-events", "")


def test_wait_terminal_exige_readback_independente(monkeypatch):
    monkeypatch.setattr(
        cycle,
        "request_json",
        lambda *args, **kwargs: (
            200,
            {"status": "completed", "resultado": {"readback_verified": False}},
        ),
    )

    with pytest.raises(RuntimeError, match="conclusao_sem_readback_independente"):
        cycle.wait_terminal(
            "https://runtime.example",
            "/api/todo-events/event-1",
            "",
            timeout_seconds=1,
            poll_seconds=0,
        )


def test_resolve_runtime_url_preserva_prefixo_publico() -> None:
    assert cycle.resolve_runtime_url(
        "https://runtime.example/runtime-core",
        "/api/todo-events/event-1",
    ) == "https://runtime.example/runtime-core/api/todo-events/event-1"
