from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import todo_global_chat_event_gateway as gateway

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"


def _event() -> dict:
    return {
        "schema_version": "1.0",
        "event_id": "chatgpt-todo-test-001",
        "event_type": "todo.updated",
        "occurred_at": datetime(2026, 9, 28, 1, 0, tzinfo=timezone.utc).isoformat(),
        "correlation_id": "chatgpt-correlation-test-001",
        "idempotency_key": "a" * 64,
        "project": "Engineering Control Plane",
        "producer": "chatgpt",
        "todo": {
            "title": "Validar gateway TodoEvent do chat",
            "type": "Validação",
            "external_id": "github:reqsys-engineering-orchestrator#42",
            "status": "EM ANDAMENTO",
            "priority": "P0",
            "next_action": "Executar E2E governado.",
            "completion_criteria": "Readback e replay idempotente.",
            "evidence": "Teste controlado.",
            "e2e_status": "PARCIAL",
            "origin": "ChatGPT",
            "source": "ChatGPT",
        },
    }


def _encode(event: dict) -> str:
    raw = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _github_event(event: dict | None = None) -> dict:
    encoded = _encode(event or _event())
    return {
        "issue": {"number": 1705},
        "comment": {
            "id": 987,
            "user": {"login": "ericson-j-santos"},
            "body": gateway.COMMAND_PREFIX + encoded,
        },
    }


def test_extract_event_accepts_owner_issue_and_strict_payload() -> None:
    event = gateway.extract_event(_github_event())
    assert event["event_id"] == "chatgpt-todo-test-001"
    assert event["producer"] == "chatgpt"
    assert event["todo"]["external_id"].endswith("#42")


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("issue", {"number": 999}, "unauthorized_issue"),
        (
            "comment",
            {"id": 987, "user": {"login": "other"}, "body": gateway.COMMAND_PREFIX + _encode(_event())},
            "unauthorized_actor",
        ),
    ],
)
def test_extract_event_fails_closed_for_wrong_source(field, value, error) -> None:
    payload = _github_event()
    payload[field] = value
    with pytest.raises(gateway.ChatTodoEventError, match=error):
        gateway.extract_event(payload)


def test_validate_event_rejects_hidden_execution_surface() -> None:
    event = _event()
    event["automation_action"] = {"type": "shell", "command": "echo forbidden"}
    with pytest.raises(gateway.ChatTodoEventError, match="event_unknown_fields"):
        gateway.validate_event(event)

    event = _event()
    event["todo"]["execution_request"] = {"command": "echo forbidden"}
    with pytest.raises(gateway.ChatTodoEventError, match="todo_unknown_fields"):
        gateway.validate_event(event)


def test_validate_event_rejects_blocked_without_blocker_and_next_action() -> None:
    event = _event()
    event["todo"]["status"] = "BLOQUEADO"
    event["todo"].pop("next_action")
    with pytest.raises(
        gateway.ChatTodoEventError,
        match="blocked_todo_requires_blocker_and_next_action",
    ):
        gateway.validate_event(event)


def test_publish_requires_negative_control_readback_and_idempotent_replay(monkeypatch) -> None:
    event = _event()
    calls: list[str] = []

    monkeypatch.setattr(
        gateway.cycle,
        "assert_negative_control",
        lambda endpoint, token: calls.append("negative"),
    )

    responses = iter(
        [
            {
                "event_id": event["event_id"],
                "job_id": "job-1",
                "correlation_id": event["correlation_id"],
                "idempotency_key": event["idempotency_key"],
                "status_url": "/api/todo-events/" + event["event_id"],
                "duplicate_event": False,
            },
            {
                "event_id": event["event_id"],
                "job_id": "job-1",
                "correlation_id": event["correlation_id"],
                "idempotency_key": event["idempotency_key"],
                "status_url": "/api/todo-events/" + event["event_id"],
                "duplicate_event": True,
            },
        ]
    )

    def fake_submit(endpoint, actual_event, token):
        calls.append("submit")
        assert actual_event == event
        return next(responses)

    monkeypatch.setattr(gateway.cycle, "submit", fake_submit)
    monkeypatch.setattr(
        gateway.cycle,
        "wait_terminal",
        lambda *args, **kwargs: {
            "status": "completed",
            "resultado": {"readback_verified": True},
        },
    )

    evidence = gateway.publish(
        "https://runtime.example/runtime-core",
        event,
        "masked-token",
        timeout_seconds=1,
        poll_seconds=0,
    )

    assert calls == ["negative", "submit", "submit"]
    assert evidence["readback_verified"] is True
    assert evidence["replay_duplicate_event"] is True
    assert evidence["job_id"] == "job-1"


def test_publish_rejects_replay_that_creates_second_job(monkeypatch) -> None:
    event = _event()
    monkeypatch.setattr(gateway.cycle, "assert_negative_control", lambda *args: None)
    responses = iter(
        [
            {
                "event_id": event["event_id"],
                "job_id": "job-1",
                "correlation_id": event["correlation_id"],
                "idempotency_key": event["idempotency_key"],
                "status_url": "/api/todo-events/" + event["event_id"],
            },
            {
                "event_id": event["event_id"],
                "job_id": "job-2",
                "correlation_id": event["correlation_id"],
                "idempotency_key": event["idempotency_key"],
                "status_url": "/api/todo-events/" + event["event_id"],
                "duplicate_event": True,
            },
        ]
    )
    monkeypatch.setattr(gateway.cycle, "submit", lambda *args: next(responses))
    monkeypatch.setattr(
        gateway.cycle,
        "wait_terminal",
        lambda *args, **kwargs: {"status": "completed"},
    )

    with pytest.raises(gateway.ChatTodoEventError, match="replay_created_second_job"):
        gateway.publish(
            "https://runtime.example/runtime-core",
            event,
            "masked-token",
            timeout_seconds=1,
            poll_seconds=0,
        )


def test_workflow_is_owner_scoped_same_sha_and_never_executes_comment_body() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "issue_comment:" in text
    assert "github.event.issue.number == 1705" in text
    assert "github.event.comment.user.login == 'ericson-j-santos'" in text
    assert "startsWith(github.event.comment.body, '/reqsys todo-event-v1 ')" in text
    assert "pull_request_target" not in text
    assert "environment: development" in text
    assert "id-token: write" in text
    assert "reqsys-pc24x7-todo-runtime-producer-token" in text
    assert "resolve_pc24x7_dev_locator.mjs" in text
    assert "/api/runtime/build-info" in text
    assert "/runtime-core/api/runtime/build-info" in text
    assert "--github-event-path \"$GITHUB_EVENT_PATH\"" in text
    assert "eval " not in text
    assert "TODO_GLOBAL_RUNTIME_TOKEN" in text
    assert "publish-todo-event:" in text
    assert "pytest==9.0.3 PyYAML==6.0.3" in text
    assert "todo-global-chat-event-" in text


def test_workflow_actions_are_immutable() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in text
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in text
    assert "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020" in text
    assert "azure/login@a641126d1b8aa4d1fa005f4f92df94a3a4c4c906" in text
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in text
