#!/usr/bin/env python3
"""Publica um TodoEvent v1 vindo do chat pelo gateway governado do GitHub."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts import todo_global_hourly_cycle as cycle

COMMAND_PREFIX = "/reqsys todo-event-v1 "
AUTHORIZED_ISSUE = 1705
AUTHORIZED_ACTOR = "ericson-j-santos"

EVENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
HEX64_RE = re.compile(r"^[a-f0-9]{64}$")
BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")

ALLOWED_EVENT_TYPES = {
    "todo.created",
    "todo.updated",
    "todo.status.changed",
    "todo.evidence.updated",
    "todo.reconcile.requested",
}
ALLOWED_STATUSES = {
    "PENDENTE",
    "EM ANDAMENTO",
    "BLOQUEADO",
    "CONCLUÍDO",
    "CANCELADO",
}
ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}
ALLOWED_E2E = {"N/A", "PENDENTE", "PARCIAL", "VALIDADO", "BLOQUEADO"}
ALLOWED_TOP_LEVEL = {
    "schema_version",
    "event_id",
    "event_type",
    "occurred_at",
    "correlation_id",
    "idempotency_key",
    "project",
    "producer",
    "todo",
}
ALLOWED_TODO_KEYS = {
    "title",
    "type",
    "external_id",
    "status",
    "priority",
    "blocker",
    "next_action",
    "completion_criteria",
    "evidence",
    "evidence_url",
    "e2e_status",
    "origin",
    "origin_url",
    "source",
}


class ChatTodoEventError(RuntimeError):
    """Falha fechada do produtor ChatGPT -> TODO Global."""


def _bounded_text(value: object, field: str, minimum: int, maximum: int) -> str:
    text = str(value or "").strip()
    if not minimum <= len(text) <= maximum:
        raise ChatTodoEventError(f"{field}_invalid")
    return text


def _optional_text(value: object, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > maximum:
        raise ChatTodoEventError(f"{field}_invalid")
    return text


def decode_event_payload(encoded: str) -> dict[str, Any]:
    token = encoded.strip()
    if not token or not BASE64URL_RE.fullmatch(token):
        raise ChatTodoEventError("payload_base64url_invalid")
    padding = "=" * ((4 - len(token) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode((token + padding).encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ChatTodoEventError("payload_decode_invalid") from exc
    if not isinstance(payload, dict):
        raise ChatTodoEventError("payload_not_object")
    return payload


def validate_event(event: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(event) - ALLOWED_TOP_LEVEL)
    if unknown:
        raise ChatTodoEventError("event_unknown_fields:" + ",".join(unknown))

    if event.get("schema_version") != "1.0":
        raise ChatTodoEventError("schema_version_invalid")
    if not EVENT_ID_RE.fullmatch(str(event.get("event_id") or "")):
        raise ChatTodoEventError("event_id_invalid")
    if event.get("event_type") not in ALLOWED_EVENT_TYPES:
        raise ChatTodoEventError("event_type_invalid")

    occurred_at = _bounded_text(event.get("occurred_at"), "occurred_at", 10, 80)
    try:
        instant = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChatTodoEventError("occurred_at_invalid") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ChatTodoEventError("occurred_at_timezone_missing")

    _bounded_text(event.get("correlation_id"), "correlation_id", 8, 128)
    if not HEX64_RE.fullmatch(str(event.get("idempotency_key") or "")):
        raise ChatTodoEventError("idempotency_key_invalid")
    _bounded_text(event.get("project"), "project", 1, 200)
    if event.get("producer") != "chatgpt":
        raise ChatTodoEventError("producer_not_chatgpt")

    todo = event.get("todo")
    if not isinstance(todo, dict):
        raise ChatTodoEventError("todo_invalid")
    unknown_todo = sorted(set(todo) - ALLOWED_TODO_KEYS)
    if unknown_todo:
        raise ChatTodoEventError("todo_unknown_fields:" + ",".join(unknown_todo))

    _bounded_text(todo.get("title"), "todo_title", 1, 500)
    _bounded_text(todo.get("type"), "todo_type", 1, 100)
    _optional_text(todo.get("external_id"), "todo_external_id", 300)
    status = todo.get("status")
    if status not in ALLOWED_STATUSES:
        raise ChatTodoEventError("todo_status_invalid")
    if todo.get("priority") is not None and todo.get("priority") not in ALLOWED_PRIORITIES:
        raise ChatTodoEventError("todo_priority_invalid")
    if todo.get("e2e_status") is not None and todo.get("e2e_status") not in ALLOWED_E2E:
        raise ChatTodoEventError("todo_e2e_status_invalid")

    for field, maximum in (
        ("blocker", 2000),
        ("next_action", 2000),
        ("completion_criteria", 2000),
        ("evidence", 4000),
        ("evidence_url", 2000),
        ("origin", 500),
        ("origin_url", 2000),
        ("source", 100),
    ):
        _optional_text(todo.get(field), f"todo_{field}", maximum)

    if status == "BLOQUEADO" and (not todo.get("blocker") or not todo.get("next_action")):
        raise ChatTodoEventError("blocked_todo_requires_blocker_and_next_action")
    if status == "CONCLUÍDO" and (
        not todo.get("completion_criteria") or not todo.get("evidence")
    ):
        raise ChatTodoEventError("completed_todo_requires_criteria_and_evidence")

    return event


def extract_event(github_event: dict[str, Any]) -> dict[str, Any]:
    issue = github_event.get("issue")
    comment = github_event.get("comment")
    if not isinstance(issue, dict) or issue.get("number") != AUTHORIZED_ISSUE:
        raise ChatTodoEventError("unauthorized_issue")
    if not isinstance(comment, dict):
        raise ChatTodoEventError("comment_missing")
    user = comment.get("user")
    if not isinstance(user, dict) or user.get("login") != AUTHORIZED_ACTOR:
        raise ChatTodoEventError("unauthorized_actor")
    body = str(comment.get("body") or "")
    if not body.startswith(COMMAND_PREFIX):
        raise ChatTodoEventError("command_prefix_invalid")
    encoded = body[len(COMMAND_PREFIX) :].strip()
    return validate_event(decode_event_payload(encoded))


def publish(
    runtime_url: str,
    event: dict[str, Any],
    token: str,
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any]:
    endpoint = runtime_url.rstrip("/") + "/api/todo-events"
    cycle.assert_negative_control(endpoint, token)
    accepted = cycle.submit(endpoint, event, token)
    terminal = cycle.wait_terminal(
        runtime_url,
        accepted["status_url"],
        token,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )
    replay = cycle.submit(endpoint, event, token)
    if replay["job_id"] != accepted["job_id"]:
        raise ChatTodoEventError("replay_created_second_job")
    if replay.get("duplicate_event") is not True:
        raise ChatTodoEventError("replay_did_not_report_duplicate")
    return {
        "result": "TODO_GLOBAL_CHAT_EVENT_VALIDATED",
        "event_id": event["event_id"],
        "correlation_id": event["correlation_id"],
        "idempotency_key": event["idempotency_key"],
        "project": event["project"],
        "external_id": event["todo"].get("external_id"),
        "job_id": accepted["job_id"],
        "terminal_status": terminal["status"],
        "readback_verified": True,
        "replay_duplicate_event": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-event-path", required=True)
    parser.add_argument("--runtime-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=180)
    parser.add_argument("--poll-seconds", type=float, default=5)
    args = parser.parse_args()

    github_event = json.loads(
        Path(args.github_event_path).read_text(encoding="utf-8")
    )
    event = extract_event(github_event)
    token = os.environ.get("TODO_GLOBAL_RUNTIME_TOKEN", "")
    if not token:
        raise ChatTodoEventError("runtime_token_missing")

    evidence = publish(
        args.runtime_url,
        event,
        token,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )
    evidence.update(
        {
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "source_issue": AUTHORIZED_ISSUE,
            "source_comment_id": (github_event.get("comment") or {}).get("id"),
            "production_touched": False,
            "secret_values_persisted": False,
        }
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
