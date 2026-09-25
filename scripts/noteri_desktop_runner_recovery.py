#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
ENDPOINT = f"http://{TARGET_HOST}:8787"
WORKER_ID = "desktop-pdqk954"
TARGET_CONTROLLER_VERSION = "0.2.53"
RECOVERY_CONTRACT_VERSION = 1
REQUIRED_TASKS = {
    "host.orchestrator.refresh.v1",
    "host.inventory.files.v1",
    "host.github_runner.recover.v1",
}
COMPLETED = "CONCLUÍDO"
TERMINAL_FAILURES = {"BLOQUEADO", "CANCELADO"}


class BridgeError(RuntimeError):
    pass


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 5.0) -> tuple[int, dict[str, Any]]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"error": f"http_{exc.code}"}
        return exc.code, body
    except URLError as exc:
        raise BridgeError(f"control_plane_unavailable:{type(exc.reason).__name__}") from exc


def validate_source_host() -> str:
    if os.name != "nt":
        raise BridgeError("windows_required")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise BridgeError(f"source_host_not_authorized:{host}")
    return host


def read_worker() -> dict[str, Any]:
    status, ready = request_json("GET", ENDPOINT + "/readyz")
    if status != 200 or ready.get("ready") is not True:
        raise BridgeError(f"desktop_orchestrator_not_ready:http_{status}")
    status, snapshot = request_json("GET", ENDPOINT + "/v1/workers")
    if status != 200:
        raise BridgeError(f"workers_read_failed:http_{status}")
    matches = [
        item for item in snapshot.get("workers", [])
        if str(item.get("worker_id", "")).casefold() == WORKER_ID.casefold()
    ]
    if len(matches) != 1:
        raise BridgeError(f"desktop_worker_count_invalid:{len(matches)}")
    worker = matches[0]
    if worker.get("fresh") is not True:
        raise BridgeError("desktop_worker_not_fresh")
    if worker.get("controller_online") is not True:
        raise BridgeError("desktop_controller_offline")
    if worker.get("auth_valid") is not True:
        raise BridgeError("desktop_worker_auth_invalid")
    if worker.get("profile") != "NORMAL":
        raise BridgeError(f"desktop_profile_not_normal:{worker.get('profile')}")
    if worker.get("controller_version") != TARGET_CONTROLLER_VERSION:
        raise BridgeError(f"controller_version_mismatch:{worker.get('controller_version')}")
    capabilities = worker.get("capabilities") or {}
    if capabilities.get("recovery_contract_version") != RECOVERY_CONTRACT_VERSION:
        raise BridgeError(
            f"recovery_contract_mismatch:{capabilities.get('recovery_contract_version')}"
        )
    safe = set(capabilities.get("safe_task_types") or [])
    missing = sorted(REQUIRED_TASKS - safe)
    if missing:
        raise BridgeError("recovery_capabilities_missing:" + ",".join(missing))
    return worker


def submit_runner_recovery(correlation_id: str) -> dict[str, Any]:
    payload = {
        "event_id": f"{correlation_id}-runner-recovery",
        "correlation_id": correlation_id,
        "idempotency_key": f"desktop-runner-recovery:{TARGET_HOST}:{TARGET_CONTROLLER_VERSION}",
        "task_type": "host.github_runner.recover.v1",
        "payload": {"target_host": TARGET_HOST},
        "risk": 2,
        "max_attempts": 1,
        "lease_seconds": 60,
    }
    status, body = request_json("POST", ENDPOINT + "/v1/intake", payload)
    if status not in {200, 201}:
        raise BridgeError(f"runner_recovery_submit_failed:http_{status}:{body.get('error')}")
    item = body.get("item") or {}
    item_id = item.get("id")
    if not item_id:
        raise BridgeError("runner_recovery_item_id_missing")
    return {
        "item_id": item_id,
        "created": bool(body.get("created")),
        "replayed": bool(body.get("replayed")),
        "dispatch": body.get("dispatch"),
    }


def wait_terminal(item_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        status, body = request_json("GET", ENDPOINT + f"/v1/work-items/{item_id}")
        if status != 200:
            raise BridgeError(f"runner_recovery_read_failed:http_{status}")
        item = body.get("item") or {}
        last = item
        state = item.get("status")
        if state == COMPLETED:
            result = item.get("result") or {}
            if result.get("handler") != "host.github_runner.recover.v1":
                raise BridgeError("runner_recovery_result_handler_mismatch")
            return item
        if state in TERMINAL_FAILURES:
            raise BridgeError(
                f"runner_recovery_terminal_failure:{state}:{item.get('last_error')}"
            )
        time.sleep(1.0)
    raise BridgeError(
        f"runner_recovery_timeout:{last.get('status')}:{last.get('last_error')}"
    )


def execute(correlation_id: str, timeout_seconds: int) -> dict[str, Any]:
    source_host = validate_source_host()
    worker_before = read_worker()
    submission = submit_runner_recovery(correlation_id)
    terminal = wait_terminal(submission["item_id"], timeout_seconds)
    worker_after = read_worker()
    return {
        "ok": True,
        "source_host": source_host,
        "target_host": TARGET_HOST,
        "endpoint": ENDPOINT,
        "controller_version": worker_after.get("controller_version"),
        "recovery_contract_version": (worker_after.get("capabilities") or {}).get("recovery_contract_version"),
        "safe_task_types": sorted((worker_after.get("capabilities") or {}).get("safe_task_types") or []),
        "worker_fresh": bool(worker_after.get("fresh")),
        "worker_eligible": bool(worker_after.get("eligible")),
        "runner_recovery_item_id": submission["item_id"],
        "runner_recovery_created": submission["created"],
        "runner_recovery_replayed": submission["replayed"],
        "runner_recovery_result": terminal.get("result") or {},
        "before_controller_version": worker_before.get("controller_version"),
        "correlation_id": correlation_id,
        "production_touched": False,
        "secrets_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        evidence = execute(args.correlation_id, args.timeout_seconds)
        code = 0
    except Exception as exc:
        evidence = {
            "ok": False,
            "source_host": socket.gethostname(),
            "target_host": TARGET_HOST,
            "endpoint": ENDPOINT,
            "correlation_id": args.correlation_id,
            "error": str(exc)[:1000],
            "error_type": type(exc).__name__,
            "production_touched": False,
            "secrets_read": False,
        }
        code = 2
    args.evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
