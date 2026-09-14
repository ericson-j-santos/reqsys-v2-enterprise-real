#!/usr/bin/env python3
"""Instrumenta tempo bloqueado por dependências externas no lead time do ReqSys.

Fonte canônica dos eventos: comentários estruturados em uma issue ledger do GitHub.
Não infere bloqueios por texto livre, ausência de execução ou diferenças de horário.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

MARKER = "<!-- reqsys-external-wait-event:v1 -->"
ALLOWED_ACTIONS = {"blocked", "unblocked"}
ALLOWED_CATEGORIES = {
    "human_gate",
    "external_provider",
    "permission_admin",
    "secret_or_credential",
    "infrastructure_external",
}


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def minutes_between(start: datetime, end: datetime) -> float:
    return round((end - start).total_seconds() / 60, 2)


def extract_event_from_comment(comment: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    body = str(comment.get("body") or "")
    if MARKER not in body:
        return None, None

    marker_index = body.index(MARKER) + len(MARKER)
    payload_text = body[marker_index:].lstrip()
    fence_index = payload_text.find("```")
    if fence_index >= 0:
        payload_text = payload_text[fence_index + 3 :].lstrip()
        if payload_text.startswith("json"):
            payload_text = payload_text[4:].lstrip()

    brace_index = payload_text.find("{")
    if brace_index < 0:
        return None, "structured_payload_missing"

    try:
        payload, _ = json.JSONDecoder().raw_decode(payload_text[brace_index:])
    except json.JSONDecodeError:
        return None, "structured_payload_invalid_json"

    if not isinstance(payload, dict):
        return None, "structured_payload_not_object"

    event = dict(payload)
    event["occurred_at"] = comment.get("created_at")
    user = comment.get("user") or {}
    event["source"] = {
        "type": "github_issue_comment",
        "comment_id": comment.get("id"),
        "html_url": comment.get("html_url"),
        "created_at": comment.get("created_at"),
        "author_login": user.get("login"),
        "author_association": comment.get("author_association"),
    }
    return event, None


def validate_event(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(event.get("event_id") or "").strip():
        errors.append("event_id_missing")
    if not str(event.get("wait_id") or "").strip():
        errors.append("wait_id_missing")
    if not str(event.get("correlation_id") or "").strip():
        errors.append("correlation_id_missing")
    if event.get("action") not in ALLOWED_ACTIONS:
        errors.append("action_invalid")
    if event.get("category") not in ALLOWED_CATEGORIES:
        errors.append("category_invalid")
    if parse_dt(event.get("occurred_at")) is None:
        errors.append("occurred_at_invalid")
    source = event.get("source") or {}
    if source.get("type") != "github_issue_comment" or not source.get("comment_id"):
        errors.append("source_invalid")
    if source.get("author_login") != "github-actions[bot]":
        errors.append("source_author_not_recorder_bot")

    run_id = str(event.get("recorder_run_id") or "").strip()
    run_attempt = str(event.get("recorder_run_attempt") or "").strip()
    if not run_id.isdigit() or not run_attempt.isdigit():
        errors.append("recorder_identity_missing")
    elif str(event.get("event_id") or "") != f"wait-{run_id}-{run_attempt}":
        errors.append("event_id_recorder_mismatch")
    return errors


def collect_structured_events(comments: list[dict[str, Any]]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    seen_semantic: set[tuple[str, str, str]] = set()
    duplicate_event_ids: list[str] = []
    duplicate_semantic: list[dict[str, str]] = []

    ordered_comments = sorted(
        comments,
        key=lambda item: (
            str(item.get("created_at") or ""),
            int(item.get("id") or 0),
        ),
    )
    for comment in ordered_comments:
        event, parse_error = extract_event_from_comment(comment)
        if event is None:
            if parse_error:
                invalid.append({"comment_id": comment.get("id"), "error": parse_error})
            continue

        errors = validate_event(event)
        if errors:
            invalid.append({
                "comment_id": comment.get("id"),
                "event_id": event.get("event_id"),
                "errors": errors,
            })
            continue

        event_id = str(event["event_id"])
        if event_id in seen_event_ids:
            duplicate_event_ids.append(event_id)
            continue
        seen_event_ids.add(event_id)

        semantic_key = (
            str(event["wait_id"]),
            str(event["action"]),
            str(event["correlation_id"]),
        )
        if semantic_key in seen_semantic:
            duplicate_semantic.append({
                "wait_id": semantic_key[0],
                "action": semantic_key[1],
                "correlation_id": semantic_key[2],
                "event_id": event_id,
            })
            continue
        seen_semantic.add(semantic_key)
        events.append(event)

    events.sort(key=lambda item: (str(item.get("occurred_at") or ""), str(item.get("event_id") or "")))
    return {
        "events": events,
        "invalid_events": invalid,
        "duplicate_event_ids": sorted(set(duplicate_event_ids)),
        "duplicate_semantic_events": duplicate_semantic,
    }


def build_wait_partition(
    comments: list[dict[str, Any]],
    collection_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    collection_status = collection_status or {"ok": True}
    if collection_status.get("ok") is not True:
        return {
            "technical_intervals_instrumented": True,
            "external_blocked_minutes": None,
            "external_wait_status": "collection_failed",
            "collection_error": collection_status.get("error") or "unknown",
            "closed_waits": 0,
            "open_waits": 0,
            "invalid_event_count": 0,
            "duplicate_event_count": 0,
            "by_category": {},
            "waits": [],
        }

    collected = collect_structured_events(comments)
    events = collected["events"]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[(str(event["wait_id"]), str(event["correlation_id"]))].append(event)

    waits: list[dict[str, Any]] = []
    invalid_sequence_count = 0
    total_closed_minutes = 0.0
    by_category: dict[str, float] = defaultdict(float)

    for (wait_id, correlation_id), group in sorted(grouped.items()):
        group.sort(key=lambda item: str(item["occurred_at"]))
        blocked = next((item for item in group if item["action"] == "blocked"), None)
        unblocked = None
        if blocked:
            blocked_at = parse_dt(blocked["occurred_at"])
            for item in group:
                if item["action"] != "unblocked":
                    continue
                candidate = parse_dt(item["occurred_at"])
                if blocked_at and candidate and candidate >= blocked_at:
                    unblocked = item
                    break

        if blocked is None:
            invalid_sequence_count += 1
            waits.append({
                "wait_id": wait_id,
                "correlation_id": correlation_id,
                "status": "invalid_sequence",
                "reason": "unblocked_without_blocked",
            })
            continue

        category = str(blocked["category"])
        if unblocked and unblocked.get("category") != blocked.get("category"):
            invalid_sequence_count += 1
            waits.append({
                "wait_id": wait_id,
                "correlation_id": correlation_id,
                "status": "invalid_sequence",
                "reason": "category_mismatch",
            })
            continue
        if (
            unblocked
            and blocked.get("sha")
            and unblocked.get("sha")
            and blocked.get("sha") != unblocked.get("sha")
        ):
            invalid_sequence_count += 1
            waits.append({
                "wait_id": wait_id,
                "correlation_id": correlation_id,
                "status": "invalid_sequence",
                "reason": "sha_mismatch",
            })
            continue

        blocked_at = parse_dt(blocked["occurred_at"])
        unblocked_at = parse_dt(unblocked["occurred_at"]) if unblocked else None
        duration = None
        if blocked_at and unblocked_at:
            duration = minutes_between(blocked_at, unblocked_at)
            total_closed_minutes += duration
            by_category[category] += duration

        waits.append({
            "wait_id": wait_id,
            "correlation_id": correlation_id,
            "category": category,
            "status": "closed" if unblocked else "open",
            "blocked_at": blocked.get("occurred_at"),
            "unblocked_at": unblocked.get("occurred_at") if unblocked else None,
            "duration_minutes": duration,
            "sha": blocked.get("sha"),
            "source_reference": blocked.get("source_reference"),
            "blocked_source": blocked.get("source"),
            "unblocked_source": unblocked.get("source") if unblocked else None,
        })

    closed_waits = sum(1 for item in waits if item.get("status") == "closed")
    open_waits = sum(1 for item in waits if item.get("status") == "open")
    duplicate_count = len(collected["duplicate_event_ids"]) + len(collected["duplicate_semantic_events"])
    invalid_count = len(collected["invalid_events"]) + invalid_sequence_count

    if not events and not invalid_count and not duplicate_count:
        status = "not_instrumented"
        external_minutes = None
    elif open_waits or invalid_count:
        status = "partial"
        external_minutes = round(total_closed_minutes, 2)
    else:
        status = "instrumented"
        external_minutes = round(total_closed_minutes, 2)

    return {
        "technical_intervals_instrumented": True,
        "external_blocked_minutes": external_minutes,
        "external_wait_status": status,
        "closed_waits": closed_waits,
        "open_waits": open_waits,
        "invalid_event_count": invalid_count,
        "duplicate_event_count": duplicate_count,
        "duplicate_event_ids": collected["duplicate_event_ids"],
        "duplicate_semantic_events": collected["duplicate_semantic_events"],
        "by_category": {key: round(value, 2) for key, value in sorted(by_category.items())},
        "waits": waits,
    }


def enrich_report(
    report: dict[str, Any],
    comments: list[dict[str, Any]],
    collection_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    delivery = report.setdefault("delivery_velocity", {})
    delivery["wait_partition"] = build_wait_partition(comments, collection_status)
    report["schema_version"] = "1.3.0"
    return report


def append_markdown(markdown: str, partition: dict[str, Any]) -> str:
    lines = [
        "",
        "## Partição de espera externa",
        "",
        f"- Status: **{partition['external_wait_status']}**",
        f"- Tempo externo fechado: **{partition['external_blocked_minutes']} min**",
        f"- Bloqueios fechados/abertos: **{partition['closed_waits']}/{partition['open_waits']}**",
        f"- Eventos inválidos/duplicados: **{partition['invalid_event_count']}/{partition['duplicate_event_count']}**",
        "",
    ]
    return markdown.rstrip() + "\n" + "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--collection-status", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()

    comments = json.loads(args.comments.read_text(encoding="utf-8"))
    collection_status = (
        json.loads(args.collection_status.read_text(encoding="utf-8"))
        if args.collection_status and args.collection_status.exists()
        else {"ok": True}
    )
    report = json.loads(args.report.read_text(encoding="utf-8"))
    enriched = enrich_report(report, comments, collection_status)
    args.report.write_text(json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.markdown.write_text(
        append_markdown(args.markdown.read_text(encoding="utf-8"), enriched["delivery_velocity"]["wait_partition"]),
        encoding="utf-8",
    )
    print(json.dumps({
        "external_wait_status": enriched["delivery_velocity"]["wait_partition"]["external_wait_status"],
        "external_blocked_minutes": enriched["delivery_velocity"]["wait_partition"]["external_blocked_minutes"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
