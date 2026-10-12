#!/usr/bin/env python3
"""Probe fixed Worker Pool DEV runtime capabilities without mutating its queue."""
from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOST = "DESKTOP-PDQK954"
POOL_URL = "http://127.0.0.1:8097"
TASK_ID = "cwp-7d84018f3319356181ab9b47"
ISSUE = 2547
REQUEST_ID = "9a9783d5ac78199eacfd13c0"
REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
TASK_BASE_SHA = "14232beac63c8d202f90bed1cf23df8680a54b2e"
ENGINE_SOURCE_SHA = "d05ad0ce7c2945db1914a400127621bce4256a8b"
EVIDENCE = ROOT / "artifacts" / "codex-worker-pool-version-read-dev" / "evidence.json"
DIAG_PATH = f"/v1/tasks/{TASK_ID}/diagnostics"
TASK_PATH = f"/v1/tasks/{TASK_ID}"
ALLOWED_PATHS = {"/health", "/openapi.json", TASK_PATH, DIAG_PATH}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
VERSION = re.compile(r"^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$")
SAFE_REASON = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
STATES = {"queued", "leased", "running", "validating", "blocked", "completed", "failed"}
RequestFn = Callable[[str, str | None], tuple[int, dict[str, Any]]]


class ProbeBlocked(RuntimeError):
    """Only enumerated codes are published; never raw HTTP or credential text."""


class RefuseRedirect(HTTPRedirectHandler):
    """Never forward a protected loopback request to a redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def current_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip().lower()


def request_json(path: str, token: str | None) -> tuple[int, dict[str, Any]]:
    if path not in ALLOWED_PATHS:
        raise ProbeBlocked("non_allowlisted_endpoint")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(POOL_URL + path, headers=headers, method="GET")
    try:
        with build_opener(ProxyHandler({}), RefuseRedirect()).open(req, timeout=12) as response:  # noqa: S310 - fixed loopback endpoint.
            body = response.read(262145)
            if len(body) > 262144:
                raise ProbeBlocked("response_size_exceeded")
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ProbeBlocked("response_shape_invalid")
            return int(response.status), payload
    except HTTPError as exc:
        if exc.code in (401, 403, 404, 503):
            return int(exc.code), {}
        raise ProbeBlocked("unexpected_http_status") from None
    except (URLError, TimeoutError, OSError, UnicodeError, ValueError):
        raise ProbeBlocked("loopback_probe_unavailable") from None


def _required_field(actual: dict[str, Any], key: str, value: Any) -> None:
    if actual.get(key) != value:
        raise ProbeBlocked("task_identity_mismatch")


def _diagnostic_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("read_mode") != "sqlite_mode_ro":
        raise ProbeBlocked("diagnostic_not_read_only")
    if payload.get("claim_performed") is not False or payload.get("reconciliation_requested") is not False:
        raise ProbeBlocked("diagnostic_mutation_claimed")
    task = payload.get("task")
    lane = payload.get("lane")
    workers = payload.get("workers")
    if not isinstance(task, dict) or not isinstance(lane, dict) or not isinstance(workers, list):
        raise ProbeBlocked("diagnostic_shape_invalid")
    for key, value in (
        ("task_id", TASK_ID), ("repository", REPOSITORY),
        ("issue_number", ISSUE), ("base_sha", TASK_BASE_SHA),
    ):
        _required_field(task, key, value)
    if task.get("state") not in STATES:
        raise ProbeBlocked("diagnostic_task_state_invalid")
    if not isinstance(lane.get("enabled"), bool) or not isinstance(lane.get("configured"), bool):
        raise ProbeBlocked("diagnostic_lane_invalid")
    if type(payload.get("precheck_eligible_workers")) is not int:
        raise ProbeBlocked("diagnostic_workers_invalid")
    if len(workers) > 250 or payload["precheck_eligible_workers"] > len(workers):
        raise ProbeBlocked("diagnostic_worker_count_invalid")
    reason_counts: dict[str, int] = {}
    by_role = {"builder": 0, "validator": 0}
    for worker in workers:
        if not isinstance(worker, dict) or worker.get("role") not in by_role:
            raise ProbeBlocked("diagnostic_worker_shape_invalid")
        by_role[worker["role"]] += 1
        reasons = worker.get("reasons")
        if not isinstance(reasons, list) or len(reasons) > 12:
            raise ProbeBlocked("diagnostic_worker_reasons_invalid")
        for reason in reasons:
            if not isinstance(reason, str) or not SAFE_REASON.fullmatch(reason):
                raise ProbeBlocked("diagnostic_reason_unsafe")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return {
        "task_state": task["state"],
        "lane_configured": lane["configured"],
        "lane_enabled": lane["enabled"],
        "lane_max_in_flight": lane.get("max_in_flight"),
        "lane_active_count": lane.get("active_count"),
        "workers_registered": len(workers),
        "builders_registered": by_role["builder"],
        "validators_registered": by_role["validator"],
        "precheck_eligible_workers": payload["precheck_eligible_workers"],
        "ineligibility_reason_counts": reason_counts,
        "required_role": payload.get("required_role"),
    }


def probe_version(
    *, expected_sha: str, observed_sha: str, host: str,
    token: str, request_fn: RequestFn,
) -> dict[str, Any]:
    if not SHA40.fullmatch(expected_sha) or observed_sha != expected_sha:
        raise ProbeBlocked("checkout_sha_mismatch")
    if host.upper() != HOST:
        raise ProbeBlocked("host_identity_refused")
    if not isinstance(token, str) or not token:
        raise ProbeBlocked("service_token_missing")
    history: list[str] = []

    def get(path: str, *, protected: bool = False) -> tuple[int, dict[str, Any]]:
        if path not in ALLOWED_PATHS:
            raise ProbeBlocked("non_allowlisted_endpoint")
        history.append("GET " + path)
        return request_fn(path, token if protected else None)

    hcode, health = get("/health")
    if hcode != 200 or health.get("status") != "healthy" or health.get("service") != "codex-worker-pool":
        raise ProbeBlocked("health_identity_not_ready")
    code, schema = get("/openapi.json")
    if code != 200:
        raise ProbeBlocked("openapi_unavailable")
    info, paths = schema.get("info"), schema.get("paths")
    if not isinstance(info, dict) or not isinstance(paths, dict):
        raise ProbeBlocked("openapi_schema_invalid")
    label, version = info.get("title"), info.get("version")
    if label not in ("ReqSys Codex Worker Pool", "Engineering Worker Pool"):
        raise ProbeBlocked("runtime_service_identity_unexpected")
    match = VERSION.fullmatch(str(version))
    if match is None:
        raise ProbeBlocked("runtime_version_invalid")
    version_tuple = tuple(int(x) for x in match.groups())
    diag_present = DIAG_PATH in paths and isinstance(paths[DIAG_PATH], dict) and "get" in paths[DIAG_PATH]
    if label == "ReqSys Codex Worker Pool" and version_tuple >= (1, 4, 0):
        raise ProbeBlocked("legacy_service_version_inconsistent")
    if label == "Engineering Worker Pool" and version_tuple < (1, 4, 0):
        raise ProbeBlocked("engineering_service_version_inconsistent")
    if version_tuple >= (1, 4, 0) and not diag_present:
        raise ProbeBlocked("modern_runtime_missing_diagnostics")
    if version_tuple < (1, 4, 0) and diag_present:
        raise ProbeBlocked("legacy_runtime_unexpected_diagnostics")
    status, task = get(TASK_PATH, protected=True)
    if status != 200:
        raise ProbeBlocked("fixed_task_read_unavailable")
    for key, value in (
        ("task_id", TASK_ID), ("issue_number", ISSUE),
        ("request_id", REQUEST_ID), ("repository", REPOSITORY),
        ("base_sha", TASK_BASE_SHA),
    ):
        _required_field(task, key, value)
    if task.get("state") not in STATES:
        raise ProbeBlocked("fixed_task_state_invalid")

    result: dict[str, Any] = {
        "schema_version": "1.0.0",
        "result": "WORKER_POOL_VERSION_PROBE_OK",
        "environment": "dev",
        "host": HOST,
        "source_sha": expected_sha,
        "reference_engine_source_sha": ENGINE_SOURCE_SHA,
        "runtime_source_sha_attested": False,
        "task_id": TASK_ID,
        "issue_number": ISSUE,
        "request_id": REQUEST_ID,
        "task_base_sha": TASK_BASE_SHA,
        "task_state": task["state"],
        "api_version": str(version),
        "runtime_title": label,
        "diagnostics_route_present": diag_present,
        "upgraded_diagnostics_available": False,
        "upgrade_required": not diag_present,
        "read_only_get_paths": history,
        "snapshot_called": False,
        "claim_performed": False,
        "requeue_performed": False,
        "runtime_mutated_by_probe": False,
        "secrets_exposed": False,
        "production_touched": False,
        "deploy_executed": False,
    }
    if diag_present:
        diag_status, diag = get(DIAG_PATH, protected=True)
        if diag_status != 200:
            raise ProbeBlocked("diagnostic_endpoint_runtime_unavailable")
        result.update(_diagnostic_summary(diag))
        result["upgraded_diagnostics_available"] = True
        result["upgrade_required"] = False
        result["read_only_get_paths"] = history
    return result


def _evidence(data: dict[str, Any]) -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fixed Worker Pool DEV version/capacity readonly probe")
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        if socket.gethostname().upper() != HOST:
            raise ProbeBlocked("host_identity_refused")
        if not SHA40.fullmatch(args.expected_sha) or current_sha() != args.expected_sha:
            raise ProbeBlocked("checkout_sha_mismatch")
        from scripts.pending_development_worker_pool_bridge import (  # noqa: PLC0415
            read_token, resolve_token_file,
        )
        token = read_token(resolve_token_file(None))
        result = probe_version(
            expected_sha=args.expected_sha,
            observed_sha=args.expected_sha,
            host=socket.gethostname(),
            token=token,
            request_fn=request_json,
        )
    except ProbeBlocked as exc:
        result = {
            "schema_version": "1.0.0", "result": "WORKER_POOL_VERSION_PROBE_BLOCKED",
            "reason": str(exc), "task_id": TASK_ID, "production_touched": False,
            "runtime_mutated_by_probe": False, "secrets_exposed": False,
        }
        _evidence(result)
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001
        result = {
            "schema_version": "1.0.0", "result": "WORKER_POOL_VERSION_PROBE_BLOCKED",
            "reason": "protected_probe_unavailable", "task_id": TASK_ID,
            "production_touched": False, "runtime_mutated_by_probe": False,
            "secrets_exposed": False,
        }
        _evidence(result)
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
        return 2
    _evidence(result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
