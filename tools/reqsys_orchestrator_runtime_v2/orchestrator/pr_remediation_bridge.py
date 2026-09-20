from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SHA40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class PrRemediationBridgeError(RuntimeError):
    pass


RequestFn = Callable[
    [str, str, str | None, dict[str, Any] | None],
    tuple[int, dict[str, Any]],
]


def validate_pool_url(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    parsed = urlparse(raw)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOOPBACK_HOSTS
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise PrRemediationBridgeError("worker_pool_url_not_loopback")
    return raw


def read_token(path: Path | None) -> str:
    if path is None:
        raise PrRemediationBridgeError("worker_pool_token_file_not_configured")
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PrRemediationBridgeError("worker_pool_token_unavailable") from exc
    if not token:
        raise PrRemediationBridgeError("worker_pool_token_empty")
    return token


def http_request(
    method: str,
    url: str,
    token: str | None,
    payload: dict[str, Any] | None,
) -> tuple[int, dict[str, Any]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8")
            decoded = json.loads(raw) if raw else {}
            return int(response.status), decoded if isinstance(decoded, dict) else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            decoded = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            decoded = {"detail": raw[:500]}
        return int(exc.code), decoded if isinstance(decoded, dict) else {}
    except (URLError, TimeoutError, OSError) as exc:
        raise PrRemediationBridgeError("worker_pool_unreachable") from exc


def _validate_payload(payload: dict[str, Any]) -> tuple[str, int, str, str]:
    repository = str(payload.get("repository") or "").strip()
    if "/" not in repository or repository.startswith("/") or repository.endswith("/"):
        raise PrRemediationBridgeError("repository_invalid")
    try:
        pr_number = int(payload.get("pr_number") or 0)
    except (TypeError, ValueError) as exc:
        raise PrRemediationBridgeError("pr_number_invalid") from exc
    if pr_number < 1:
        raise PrRemediationBridgeError("pr_number_invalid")
    expected_head_sha = str(payload.get("expected_head_sha") or "").strip().lower()
    if not SHA40.fullmatch(expected_head_sha):
        raise PrRemediationBridgeError("expected_head_sha_invalid")
    fingerprint = str(payload.get("failure_fingerprint") or "").strip().lower()
    if not HEX64.fullmatch(fingerprint):
        raise PrRemediationBridgeError("failure_fingerprint_invalid")
    return repository, pr_number, expected_head_sha, fingerprint


def _task_from_response(response: dict[str, Any]) -> dict[str, Any]:
    task = response.get("task")
    if not isinstance(task, dict) or not str(task.get("task_id") or ""):
        raise PrRemediationBridgeError("worker_pool_task_response_invalid")
    if "lease_token" in task:
        raise PrRemediationBridgeError("worker_pool_response_leaked_lease")
    return task


def handoff_pr_remediation(
    payload: dict[str, Any],
    *,
    correlation_id: str,
    pool_url: str,
    token_file: Path,
    request_fn: RequestFn = http_request,
) -> dict[str, Any]:
    repository, pr_number, expected_head_sha, fingerprint = _validate_payload(payload)
    correlation_id = str(correlation_id or "").strip()
    if not correlation_id or len(correlation_id) > 128:
        raise PrRemediationBridgeError("correlation_id_invalid")

    pool_url = validate_pool_url(pool_url)
    token = read_token(token_file)

    health_code, health = request_fn("GET", pool_url + "/health", None, None)
    if health_code != 200 or health.get("status") != "healthy":
        raise PrRemediationBridgeError("worker_pool_not_ready")

    request_id = "pr-remediate-" + fingerprint
    body = {
        "repository": repository,
        "issue_number": pr_number,
        "request_id": request_id,
        "correlation_id": correlation_id,
        "priority": 5,
        "base_sha": expected_head_sha,
        "max_attempts": 3,
    }

    first_code, first = request_fn("POST", pool_url + "/v1/tasks", token, body)
    if first_code not in {200, 201}:
        raise PrRemediationBridgeError(f"worker_pool_enqueue_http_{first_code}")
    task = _task_from_response(first)
    task_id = str(task["task_id"])

    replay_code, replay = request_fn("POST", pool_url + "/v1/tasks", token, body)
    if replay_code != 200 or replay.get("created") is not False:
        raise PrRemediationBridgeError("worker_pool_replay_not_idempotent")
    replay_task = _task_from_response(replay)
    if replay_task.get("task_id") != task_id:
        raise PrRemediationBridgeError("worker_pool_replay_task_mismatch")

    read_code, readback = request_fn(
        "GET", pool_url + f"/v1/tasks/{task_id}", token, None
    )
    if read_code != 200:
        raise PrRemediationBridgeError("worker_pool_readback_failed")
    if "lease_token" in readback:
        raise PrRemediationBridgeError("worker_pool_readback_leaked_lease")
    expected = {
        "task_id": task_id,
        "repository": repository,
        "issue_number": pr_number,
        "request_id": request_id,
        "base_sha": expected_head_sha,
    }
    if any(readback.get(key) != value for key, value in expected.items()):
        raise PrRemediationBridgeError("worker_pool_readback_mismatch")

    return {
        "handler": "github.pr.remediate.v1",
        "handoff": "codex-worker-pool",
        "task_id": task_id,
        "repository": repository,
        "pr_number": pr_number,
        "expected_head_sha": expected_head_sha,
        "request_id": request_id,
        "state": readback.get("state"),
        "created": first.get("created") is True,
        "replay_created": False,
        "independent_readback": True,
        "merge": False,
        "deploy": False,
    }
