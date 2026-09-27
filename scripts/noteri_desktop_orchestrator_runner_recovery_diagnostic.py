#!/usr/bin/env python3
"""Diagnóstico idempotente do recovery histórico do runner Desktop."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
CONTROL_PLANE_PORT = 8787
TASK_TYPE = "host.github_runner.recover.v1"
HISTORICAL_CORRELATION_ID = "desktop-runner-orchestrator-36287783270-2"
CONFIRM = "DIAGNOSE-HISTORICAL-DESKTOP-RUNNER-RECOVERY"
SAFE_ERROR_RE = re.compile(r"^[A-Za-z0-9_:\-. ]{1,240}$")


class DiagnosticError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_noteri(host: str | None = None, platform: str | None = None) -> None:
    observed_host = host or socket.gethostname()
    observed_platform = platform or os.name
    if observed_platform != "nt":
        raise DiagnosticError("windows_required")
    if observed_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise DiagnosticError("source_host_not_authorized")


def request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_seconds: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    normalized_method = str(method or "").upper()
    if normalized_method not in {"GET", "POST"}:
        raise DiagnosticError("method_not_allowlisted")
    if path not in {"/readyz", "/v1/status", "/v1/intake"} and not path.startswith(
        "/v1/work-items/"
    ):
        raise DiagnosticError("path_not_allowlisted")
    if normalized_method == "POST" and path != "/v1/intake":
        raise DiagnosticError("post_not_allowlisted")

    body = None
    headers = {"Accept": "application/json", "Cache-Control": "no-store"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"

    connection = HTTPConnection(
        TARGET_HOST,
        CONTROL_PLANE_PORT,
        timeout=max(1.0, min(timeout_seconds, 10.0)),
    )
    try:
        connection.request(normalized_method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(262144).decode("utf-8", errors="replace")
    except (OSError, HTTPException, TimeoutError) as exc:
        raise DiagnosticError("control_plane_unavailable") from exc
    finally:
        connection.close()

    try:
        decoded = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise DiagnosticError("control_plane_invalid_json") from exc
    if not isinstance(decoded, dict):
        raise DiagnosticError("control_plane_invalid_payload")
    return int(response.status), decoded


def build_historical_request() -> dict[str, Any]:
    digest = hashlib.sha256(
        f"{TASK_TYPE}|{TARGET_HOST}|{HISTORICAL_CORRELATION_ID}".encode("utf-8")
    ).hexdigest()
    return {
        "event_id": f"evt-runner-recovery-{digest[:32]}",
        "correlation_id": HISTORICAL_CORRELATION_ID,
        "idempotency_key": f"desktop-runner-recovery:{digest}",
        "task_type": TASK_TYPE,
        "payload": {
            "target_host": TARGET_HOST,
            "worker_hint": "builder",
        },
        "risk": 2,
        "max_attempts": 1,
        "lease_seconds": 60,
    }


def sanitize_error(value: Any) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    if not text:
        return "unknown"
    if not SAFE_ERROR_RE.fullmatch(text):
        return "non_allowlisted_error_shape"
    return text


def blocker_from_status(status_payload: dict[str, Any]) -> dict[str, Any] | None:
    blockers = status_payload.get("blockers")
    if not isinstance(blockers, list):
        return None
    matches = [
        item
        for item in blockers
        if isinstance(item, dict)
        and item.get("correlation_id") == HISTORICAL_CORRELATION_ID
    ]
    if len(matches) > 1:
        raise DiagnosticError("historical_blocker_not_unique")
    if not matches:
        return None
    item = matches[0]
    return {
        "work_item_id": str(item.get("id") or ""),
        "status": "BLOQUEADO",
        "last_error": sanitize_error(item.get("last_error")),
        "attempts": int(item.get("attempts") or 0),
        "source": "status_blockers",
    }


def replay_lookup(requester=request_json) -> dict[str, Any]:
    body = build_historical_request()
    status, replay = requester("POST", "/v1/intake", body)
    if status != 200:
        raise DiagnosticError(f"historical_replay_http_{status}")
    if replay.get("replayed") is not True:
        raise DiagnosticError("historical_replay_would_mutate")
    if replay.get("dispatch") is not None:
        raise DiagnosticError("historical_replay_redispatched")
    item = replay.get("item")
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        raise DiagnosticError("historical_replay_item_missing")
    item_id = item["id"]

    read_status, snapshot = requester("GET", f"/v1/work-items/{item_id}")
    observed = snapshot.get("item") if isinstance(snapshot, dict) else None
    if read_status != 200 or not isinstance(observed, dict):
        raise DiagnosticError("historical_work_item_read_failed")
    if observed.get("correlation_id") != HISTORICAL_CORRELATION_ID:
        raise DiagnosticError("historical_work_item_correlation_mismatch")
    if observed.get("task_type") != TASK_TYPE:
        raise DiagnosticError("historical_work_item_task_mismatch")
    if observed.get("status") != "BLOQUEADO":
        raise DiagnosticError("historical_work_item_status_changed")
    return {
        "work_item_id": item_id,
        "status": "BLOQUEADO",
        "last_error": sanitize_error(observed.get("last_error")),
        "attempts": int(observed.get("attempts") or 0),
        "source": "idempotent_replay_get",
    }


def diagnose(
    *,
    confirm: str,
    evidence_file: Path,
    requester=request_json,
    source_host: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise DiagnosticError("confirmation_invalid")
    require_noteri(source_host, platform)

    ready_status, ready = requester("GET", "/readyz")
    if ready_status != 200 or ready.get("ready") is not True:
        raise DiagnosticError("orchestrator_not_ready")
    status_code, status = requester("GET", "/v1/status")
    if status_code != 200:
        raise DiagnosticError(f"orchestrator_status_http_{status_code}")

    blocker = blocker_from_status(status)
    replay_used = False
    if blocker is None:
        blocker = replay_lookup(requester)
        replay_used = True

    evidence = {
        "schema_version": "1",
        "ok": True,
        "result": "HISTORICAL_DESKTOP_RUNNER_RECOVERY_DIAGNOSED",
        "generated_at": now_iso(),
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "control_plane_port": CONTROL_PLANE_PORT,
        "task_type": TASK_TYPE,
        "historical_correlation_id": HISTORICAL_CORRELATION_ID,
        "work_item_id": blocker["work_item_id"],
        "work_item_status": blocker["status"],
        "last_error": blocker["last_error"],
        "attempts": blocker["attempts"],
        "lookup_source": blocker["source"],
        "idempotent_replay_used": replay_used,
        "redispatch_performed": False,
        "physical_recovery_repeated": False,
        "remote_shell_used": False,
        "credentials_supplied": False,
        "secrets_read": False,
        "production_touched": False,
        "reboot_performed": False,
    }
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = diagnose(
            confirm=args.confirm,
            evidence_file=args.evidence_file.resolve(),
        )
    except (DiagnosticError, OSError, ValueError) as exc:
        evidence = {
            "schema_version": "1",
            "ok": False,
            "result": "HISTORICAL_DESKTOP_RUNNER_RECOVERY_DIAGNOSTIC_BLOCKED",
            "generated_at": now_iso(),
            "reason": str(exc)[:160],
            "historical_correlation_id": HISTORICAL_CORRELATION_ID,
            "redispatch_performed": False,
            "physical_recovery_repeated": False,
            "remote_shell_used": False,
            "credentials_supplied": False,
            "secrets_read": False,
            "production_touched": False,
            "reboot_performed": False,
        }
        args.evidence_file.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.resolve().write_text(
            json.dumps(evidence, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(evidence, sort_keys=True))
        return 2
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
