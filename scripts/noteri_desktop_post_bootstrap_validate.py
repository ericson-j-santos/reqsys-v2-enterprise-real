from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ENDPOINT = "http://DESKTOP-PDQK954:8787"
TARGET_HOST = "DESKTOP-PDQK954"
TASK_TYPE = "host.inventory.files.v1"
SCOPE = "reqsys-control-plane"
REQUIRED_CAPABILITIES = {
    "host.inventory.files.v1",
    "host.orchestrator.refresh.v1",
    "host.github_runner.recover.v1",
}
TERMINAL = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}
CONFIRM = "VALIDATE-DESKTOP-STABLE-BOOTSTRAP"


class ValidationError(RuntimeError):
    pass


def call(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    if not path.startswith("/") or "://" in path:
        raise ValidationError("path_not_allowed")
    raw = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT + path,
        data=raw,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json", "Cache-Control": "no-store"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5.0) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            return int(response.status), parsed if isinstance(parsed, dict) else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {}
        return int(exc.code), parsed if isinstance(parsed, dict) else {}
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"transport_error:{type(exc).__name__}") from exc


def desktop_worker() -> dict[str, Any]:
    status, payload = call("GET", "/v1/workers")
    if status != 200:
        raise ValidationError(f"workers_http_{status}")
    workers = payload.get("workers")
    if not isinstance(workers, list):
        raise ValidationError("workers_invalid")
    matches = [
        worker for worker in workers
        if isinstance(worker, dict)
        and str(worker.get("device_name") or "").casefold() == TARGET_HOST.casefold()
    ]
    if len(matches) != 1:
        raise ValidationError("desktop_worker_not_unique")
    worker = matches[0]
    caps = worker.get("capabilities")
    safe = caps.get("safe_task_types") if isinstance(caps, dict) else []
    safe_set = {str(item) for item in safe} if isinstance(safe, list) else set()
    missing = sorted(REQUIRED_CAPABILITIES - safe_set)
    if worker.get("fresh") is not True:
        raise ValidationError("desktop_worker_not_fresh")
    if worker.get("eligible") is not True:
        raise ValidationError("desktop_worker_not_eligible")
    if missing:
        raise ValidationError("required_capabilities_missing:" + ",".join(missing))
    return {
        "worker_id": str(worker.get("worker_id") or ""),
        "device_name": str(worker.get("device_name") or ""),
        "controller_version": str(worker.get("controller_version") or ""),
        "fresh": True,
        "eligible": True,
        "required_capabilities_present": True,
        "safe_task_types": sorted(safe_set),
        "recovery_contract_version": (
            str(caps.get("recovery_contract_version") or "")
            if isinstance(caps, dict)
            else ""
        ),
    }


def validate(correlation_id: str, timeout_seconds: int = 90) -> dict[str, Any]:
    correlation = str(correlation_id or "").strip()
    if not 8 <= len(correlation) <= 160:
        raise ValidationError("correlation_id_invalid")

    ready_status, ready = call("GET", "/readyz")
    if ready_status != 200 or ready.get("ready") is not True:
        raise ValidationError("orchestrator_not_ready")

    worker = desktop_worker()
    event_id = f"{correlation}-inventory"
    status, accepted = call(
        "POST",
        "/v1/intake",
        {
            "event_id": event_id,
            "correlation_id": correlation,
            "idempotency_key": f"desktop-post-bootstrap-inventory:{correlation}",
            "task_type": TASK_TYPE,
            "payload": {
                "target_host": TARGET_HOST,
                "scope": SCOPE,
            },
            "risk": 1,
            "max_attempts": 1,
            "lease_seconds": 90,
        },
    )
    if status not in {200, 201}:
        raise ValidationError(f"inventory_intake_http_{status}")
    item = accepted.get("item")
    if not isinstance(item, dict) or not item.get("id"):
        raise ValidationError("inventory_item_missing")

    item_id = str(item["id"])
    observed = item
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        state = str(observed.get("status") or "")
        if state in TERMINAL:
            break
        time.sleep(2)
        read_status, snapshot = call("GET", f"/v1/work-items/{item_id}")
        if read_status != 200:
            raise ValidationError(f"inventory_read_http_{read_status}")
        loaded = snapshot.get("item")
        if not isinstance(loaded, dict):
            raise ValidationError("inventory_item_invalid")
        observed = loaded

    if str(observed.get("status") or "") != "CONCLUÍDO":
        raise ValidationError(
            "inventory_not_completed:"
            + str(observed.get("status") or "timeout")
            + ":"
            + str(observed.get("last_error") or "")[:180]
        )

    result = observed.get("result")
    if not isinstance(result, dict):
        raise ValidationError("inventory_result_missing")
    if result.get("handler") != TASK_TYPE:
        raise ValidationError("inventory_handler_mismatch")
    if str(result.get("host") or "").casefold() != TARGET_HOST.casefold():
        raise ValidationError("inventory_host_mismatch")
    if result.get("scope") != SCOPE:
        raise ValidationError("inventory_scope_mismatch")
    if result.get("file_contents_read") is not False:
        raise ValidationError("inventory_file_contents_contract_violation")
    if result.get("secrets_read") is not False:
        raise ValidationError("inventory_secrets_contract_violation")
    if result.get("production_touched") is not False:
        raise ValidationError("inventory_production_contract_violation")

    matches = result.get("matches")
    if not isinstance(matches, list):
        raise ValidationError("inventory_matches_invalid")

    return {
        "ok": True,
        "endpoint": ENDPOINT,
        "target_host": TARGET_HOST,
        "correlation_id": correlation,
        "worker": worker,
        "inventory": {
            "work_item_id": item_id,
            "created": bool(accepted.get("created")),
            "replayed": bool(accepted.get("replayed")),
            "handler": result.get("handler"),
            "scope": result.get("scope"),
            "roots_checked": result.get("roots_checked"),
            "match_count": result.get("match_count"),
            "matches": matches,
            "truncated": result.get("truncated"),
            "scanned_entries": result.get("scanned_entries"),
            "file_contents_read": False,
            "secrets_read": False,
            "production_touched": False,
        },
        "stable_bootstrap_capabilities_validated": True,
        "remote_shell_used": False,
        "reboot_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    if args.confirm != CONFIRM:
        return 2
    try:
        payload = validate(args.correlation_id)
        code = 0
    except Exception as exc:
        payload = {
            "ok": False,
            "target_host": TARGET_HOST,
            "endpoint": ENDPOINT,
            "correlation_id": args.correlation_id,
            "error": str(exc)[:500],
            "remote_shell_used": False,
            "reboot_performed": False,
            "production_touched": False,
        }
        code = 3

    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
