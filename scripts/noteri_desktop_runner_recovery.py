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
ORCHESTRATOR_SHA = "4dbc927595a40fc2fd6b207c0d53fd6e895049ae"
BOOTSTRAP_TASK = "host.github_runner.bootstrap.v1"
BASE_REQUIRED_TASKS = {
    "host.orchestrator.refresh.v1",
    "host.inventory.files.v1",
    "host.github_runner.recover.v1",
}
COMPLETED = "CONCLUÍDO"
TERMINAL_FAILURES = {"BLOQUEADO", "CANCELADO"}


class BridgeError(RuntimeError):
    pass


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict[str, Any]]:
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
        raise BridgeError(
            f"control_plane_unavailable:{type(exc.reason).__name__}"
        ) from exc


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
        item
        for item in snapshot.get("workers", [])
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
        raise BridgeError(
            f"controller_version_mismatch:{worker.get('controller_version')}"
        )
    capabilities = worker.get("capabilities") or {}
    if capabilities.get("recovery_contract_version") != RECOVERY_CONTRACT_VERSION:
        raise BridgeError(
            "recovery_contract_mismatch:"
            + str(capabilities.get("recovery_contract_version"))
        )
    safe = set(capabilities.get("safe_task_types") or [])
    missing = sorted(BASE_REQUIRED_TASKS - safe)
    if missing:
        raise BridgeError("recovery_capabilities_missing:" + ",".join(missing))
    return worker


def submit_task(
    *,
    task_type: str,
    payload: dict[str, Any],
    correlation_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    body = {
        "event_id": f"{correlation_id}:{task_type}",
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "task_type": task_type,
        "payload": payload,
        "risk": 2,
        "max_attempts": 1,
        "lease_seconds": 60,
    }
    status, response = request_json("POST", ENDPOINT + "/v1/intake", body)
    if status not in {200, 201}:
        raise BridgeError(
            f"task_submit_failed:{task_type}:http_{status}:{response.get('error')}"
        )
    item = response.get("item") or {}
    item_id = item.get("id")
    if not item_id:
        raise BridgeError(f"task_item_id_missing:{task_type}")
    return {
        "item_id": item_id,
        "created": bool(response.get("created")),
        "replayed": bool(response.get("replayed")),
        "dispatch": response.get("dispatch"),
    }


def wait_terminal(
    item_id: str,
    expected_handler: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        status, body = request_json("GET", ENDPOINT + f"/v1/work-items/{item_id}")
        if status != 200:
            raise BridgeError(f"task_read_failed:http_{status}")
        item = body.get("item") or {}
        last = item
        state = item.get("status")
        if state == COMPLETED:
            result = item.get("result") or {}
            if result.get("handler") != expected_handler:
                raise BridgeError(
                    f"task_result_handler_mismatch:{expected_handler}:"
                    f"{result.get('handler')}"
                )
            return item
        if state in TERMINAL_FAILURES:
            raise BridgeError(
                f"task_terminal_failure:{expected_handler}:{state}:"
                f"{item.get('last_error')}"
            )
        time.sleep(1.0)
    raise BridgeError(
        f"task_timeout:{expected_handler}:{last.get('status')}:"
        f"{last.get('last_error')}"
    )


def wait_for_capability(task_type: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not_observed"
    while time.monotonic() < deadline:
        try:
            worker = read_worker()
            safe = set((worker.get("capabilities") or {}).get("safe_task_types") or [])
            if task_type in safe:
                return worker
            last_error = "capability_missing"
        except BridgeError as exc:
            last_error = str(exc)
        time.sleep(2.0)
    raise BridgeError(f"capability_activation_timeout:{task_type}:{last_error}")


def ensure_bootstrap_capability(correlation_id: str) -> dict[str, Any]:
    before = read_worker()
    safe = set((before.get("capabilities") or {}).get("safe_task_types") or [])
    if BOOTSTRAP_TASK in safe:
        return {
            "refreshed": False,
            "refresh_submission": None,
            "refresh_result": None,
            "worker": before,
        }

    submission = submit_task(
        task_type="host.orchestrator.refresh.v1",
        payload={
            "target_host": TARGET_HOST,
            "expected_sha": ORCHESTRATOR_SHA,
        },
        correlation_id=f"{correlation_id}-refresh",
        idempotency_key=f"desktop-orchestrator-refresh:{TARGET_HOST}:{ORCHESTRATOR_SHA}",
    )
    terminal = wait_terminal(
        submission["item_id"],
        "host.orchestrator.refresh.v1",
        45,
    )
    worker = wait_for_capability(BOOTSTRAP_TASK, 120)
    return {
        "refreshed": True,
        "refresh_submission": submission,
        "refresh_result": terminal.get("result") or {},
        "worker": worker,
    }


def execute(correlation_id: str, timeout_seconds: int) -> dict[str, Any]:
    source_host = validate_source_host()
    before = read_worker()
    activation = ensure_bootstrap_capability(correlation_id)

    bootstrap = submit_task(
        task_type=BOOTSTRAP_TASK,
        payload={"target_host": TARGET_HOST},
        correlation_id=f"{correlation_id}-bootstrap",
        idempotency_key=f"desktop-runner-bootstrap:{TARGET_HOST}:{ORCHESTRATOR_SHA}",
    )
    terminal = wait_terminal(
        bootstrap["item_id"],
        BOOTSTRAP_TASK,
        timeout_seconds,
    )
    after = read_worker()
    result = terminal.get("result") or {}
    if result.get("local_listener_verified") is not True:
        raise BridgeError("runner_listener_not_verified")
    if result.get("pickup_required") is not True:
        raise BridgeError("runner_pickup_contract_missing")

    return {
        "ok": True,
        "source_host": source_host,
        "target_host": TARGET_HOST,
        "endpoint": ENDPOINT,
        "orchestrator_target_sha": ORCHESTRATOR_SHA,
        "controller_version": after.get("controller_version"),
        "recovery_contract_version": (
            after.get("capabilities") or {}
        ).get("recovery_contract_version"),
        "safe_task_types": sorted(
            (after.get("capabilities") or {}).get("safe_task_types") or []
        ),
        "worker_fresh": bool(after.get("fresh")),
        "worker_eligible": bool(after.get("eligible")),
        "refresh_performed": bool(activation["refreshed"]),
        "refresh_result": activation["refresh_result"],
        "runner_bootstrap_item_id": bootstrap["item_id"],
        "runner_bootstrap_created": bootstrap["created"],
        "runner_bootstrap_replayed": bootstrap["replayed"],
        "runner_bootstrap_result": result,
        "before_controller_version": before.get("controller_version"),
        "correlation_id": correlation_id,
        "production_touched": False,
        "secrets_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=60)
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
            "orchestrator_target_sha": ORCHESTRATOR_SHA,
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
