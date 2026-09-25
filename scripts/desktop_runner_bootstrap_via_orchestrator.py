#!/usr/bin/env python3
"""Bootstrap do runner GitHub do Desktop via Engineering Orchestrator, a partir do Noteri."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
TARGET_WORKER = "desktop-pdqk954"
ENDPOINT = "http://DESKTOP-PDQK954:8787"
TASK_TYPE = "host.github_runner.bootstrap.v1"
CONFIRM = "BOOTSTRAP-DESKTOP-GITHUB-RUNNER-VIA-ORCHESTRATOR"
TERMINAL = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}


class BootstrapError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())[:limit]


def require_noteri(host: str | None = None, platform: str | None = None) -> None:
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise BootstrapError(f"source_host_not_allowed:{actual_host}")
    if actual_platform != "nt":
        raise BootstrapError("windows_required")


def request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(ENDPOINT + path, data=body, method=method, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            if not isinstance(data, dict):
                raise BootstrapError("control_plane_response_not_object")
            return response.status, data
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"error": "non_json_http_error"}
        return exc.code, data
    except URLError as exc:
        raise BootstrapError(f"control_plane_unavailable:{type(exc.reason).__name__}") from exc


def parse_version(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.split("."))
    except (AttributeError, ValueError) as exc:
        raise BootstrapError("controller_version_invalid") from exc


def worker_preflight() -> dict[str, Any]:
    ready_status, ready = request_json("GET", "/readyz")
    if ready_status != 200 or ready.get("ready") is not True:
        raise BootstrapError("orchestrator_not_ready")

    status_code, status = request_json("GET", "/v1/status")
    if status_code != 200:
        raise BootstrapError(f"orchestrator_status_http_{status_code}")
    workers = status.get("workers", {}).get("workers", [])
    matches = [w for w in workers if str(w.get("worker_id", "")).casefold() == TARGET_WORKER]
    if len(matches) != 1:
        raise BootstrapError("desktop_worker_not_unique")
    worker = matches[0]
    if str(worker.get("device_name", "")).casefold() != TARGET_HOST.casefold():
        raise BootstrapError("desktop_worker_device_mismatch")
    if worker.get("fresh") is not True or worker.get("eligible") is not True:
        raise BootstrapError("desktop_worker_not_eligible")
    if parse_version(str(worker.get("controller_version", ""))) < (0, 2, 53):
        raise BootstrapError("desktop_controller_too_old")

    capabilities = worker.get("capabilities")
    if not isinstance(capabilities, dict):
        raise BootstrapError("desktop_capabilities_invalid")
    if capabilities.get("recovery_contract_version") != 1:
        raise BootstrapError("desktop_recovery_contract_not_v1")
    safe_tasks = capabilities.get("safe_task_types")
    if not isinstance(safe_tasks, list) or TASK_TYPE not in safe_tasks:
        raise BootstrapError("desktop_runner_bootstrap_capability_missing")

    return {
        "worker_id": worker.get("worker_id"),
        "device_name": worker.get("device_name"),
        "controller_version": worker.get("controller_version"),
        "recovery_contract_version": capabilities.get("recovery_contract_version"),
        "fresh": worker.get("fresh"),
        "eligible": worker.get("eligible"),
        "capability_present": True,
    }


def build_intake(correlation_id: str) -> dict[str, Any]:
    logical = f"{TASK_TYPE}|{TARGET_HOST}|{correlation_id}"
    digest = hashlib.sha256(logical.encode("utf-8")).hexdigest()
    return {
        "event_id": f"runner-bootstrap-{digest}",
        "correlation_id": correlation_id,
        "idempotency_key": f"runner-bootstrap-{digest}",
        "task_type": TASK_TYPE,
        "payload": {"target_host": TARGET_HOST},
        "risk": 2,
        "max_attempts": 1,
        "lease_seconds": 90,
    }


def validate_dispatch(response: dict[str, Any]) -> str:
    dispatch = response.get("dispatch")
    if not isinstance(dispatch, dict):
        raise BootstrapError("runner_bootstrap_not_dispatched")
    worker = dispatch.get("worker")
    if not isinstance(worker, dict) or worker.get("worker_id") != TARGET_WORKER:
        raise BootstrapError("runner_bootstrap_dispatched_to_wrong_worker")
    item = response.get("item")
    if not isinstance(item, dict) or not item.get("id"):
        raise BootstrapError("runner_bootstrap_item_missing")
    return str(item["id"])


def await_terminal(item_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status = ""
    while time.monotonic() < deadline:
        status_code, payload = request_json("GET", f"/v1/work-items/{item_id}")
        if status_code != 200:
            raise BootstrapError(f"work_item_http_{status_code}")
        item = payload.get("item")
        if not isinstance(item, dict):
            raise BootstrapError("work_item_invalid")
        last_status = str(item.get("status") or "")
        if last_status in TERMINAL:
            return item
        time.sleep(2)
    raise BootstrapError(f"work_item_timeout:last_status={sanitize(last_status)}")


def validate_result(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("status") != "CONCLUÍDO":
        raise BootstrapError(
            "runner_bootstrap_terminal_failure:"
            + sanitize(item.get("last_error") or item.get("status"))
        )
    result = item.get("result")
    if not isinstance(result, dict):
        raise BootstrapError("runner_bootstrap_result_missing")
    checks = {
        "handler": result.get("handler") == TASK_TYPE,
        "host": str(result.get("host", "")).casefold() == TARGET_HOST.casefold(),
        "worker_id": result.get("worker_id") == TARGET_WORKER,
        "local_listener_verified": result.get("local_listener_verified") is True,
        "pickup_required": result.get("pickup_required") is True,
        "github_connectivity_not_claimed": result.get("github_connectivity_verified") is False,
        "production_untouched": result.get("production_touched") is False,
        "secrets_not_read": result.get("secrets_read") is False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise BootstrapError("runner_bootstrap_result_invalid:" + ",".join(failed))
    return {
        "handler": result.get("handler"),
        "host": result.get("host"),
        "worker_id": result.get("worker_id"),
        "runner_home": result.get("runner_home"),
        "listener_pid": result.get("listener_pid"),
        "local_listener_verified": True,
        "pickup_required": True,
        "github_connectivity_verified": False,
        "production_touched": False,
        "secrets_read": False,
    }


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def execute(
    *,
    confirm: str,
    correlation_id: str,
    timeout_seconds: int,
    evidence_file: Path,
    source_host: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise BootstrapError("confirmation_invalid")
    if not 30 <= timeout_seconds <= 180:
        raise BootstrapError("timeout_seconds_out_of_range")
    if not correlation_id or len(correlation_id) > 128:
        raise BootstrapError("correlation_id_invalid")
    require_noteri(source_host, platform)

    preflight = worker_preflight()
    intake = build_intake(correlation_id)
    status_code, submitted = request_json("POST", "/v1/intake", intake)
    if status_code != 201 or submitted.get("replayed") is not False:
        raise BootstrapError(f"runner_bootstrap_intake_invalid:http={status_code}")
    item_id = validate_dispatch(submitted)
    terminal = await_terminal(item_id, timeout_seconds)
    result = validate_result(terminal)

    replay_status, replay = request_json("POST", "/v1/intake", intake)
    if replay_status != 200 or replay.get("replayed") is not True:
        raise BootstrapError("runner_bootstrap_replay_not_idempotent")
    replay_item = replay.get("item")
    if not isinstance(replay_item, dict) or replay_item.get("id") != item_id:
        raise BootstrapError("runner_bootstrap_replay_item_mismatch")
    if replay.get("dispatch") is not None:
        raise BootstrapError("runner_bootstrap_replay_redispatched")

    evidence = {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "ok": True,
        "result": "DESKTOP_GITHUB_RUNNER_LOCAL_BOOTSTRAP_VERIFIED",
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "endpoint": ENDPOINT,
        "correlation_id": correlation_id,
        "preflight": preflight,
        "work_item_id": item_id,
        "work_item_status": terminal.get("status"),
        "bootstrap": result,
        "replay": {"replayed": True, "same_work_item": True, "redispatched": False},
        "pickup_required": True,
        "production_touched": False,
        "secrets_read": False,
    }
    write_evidence(evidence_file, evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("artifacts/desktop-runner-bootstrap/evidence.json"),
    )
    args = parser.parse_args()
    try:
        result = execute(
            confirm=args.confirm,
            correlation_id=args.correlation_id,
            timeout_seconds=args.timeout_seconds,
            evidence_file=args.evidence_file.resolve(),
        )
    except (BootstrapError, OSError, ValueError) as exc:
        blocked = {
            "schema_version": "1",
            "generated_at_utc": now_iso(),
            "ok": False,
            "result": "DESKTOP_GITHUB_RUNNER_BOOTSTRAP_BLOCKED",
            "error": sanitize(exc),
            "source_host": EXPECTED_SOURCE_HOST,
            "target_host": TARGET_HOST,
            "correlation_id": args.correlation_id,
            "pickup_required": True,
            "production_touched": False,
            "secrets_read": False,
        }
        write_evidence(args.evidence_file.resolve(), blocked)
        print(json.dumps(blocked, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
