#!/usr/bin/env python3
"""Bridge fail-closed entre o Pending Development Orchestrator e o Codex Worker Pool."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pending_development_local_codex import (  # noqa: E402
    LOCAL_CODEX_ROUTE,
    local_codex_request_id,
)

SHA40 = re.compile(r"^[0-9a-f]{40}$")
ELIGIBLE_STATUSES = {"dispatched", "already_dispatched"}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class BridgeError(RuntimeError):
    pass


RequestFn = Callable[[str, str, str, dict[str, Any] | None], tuple[int, dict[str, Any]]]


def load_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeError("orchestrator_report_unavailable") from exc
    if not isinstance(payload, dict):
        raise BridgeError("orchestrator_report_invalid")
    return payload


def direct_report(
    repository: str,
    issue_number: int,
    base_branch: str,
    correlation_id: str,
) -> dict[str, Any]:
    repository = repository.strip()
    base_branch = base_branch.strip()
    correlation_id = correlation_id.strip()
    if "/" not in repository or issue_number < 1 or not base_branch or not correlation_id:
        raise BridgeError("orchestrator_identity_invalid")
    return {
        "schema_version": "1.0.0",
        "correlation_id": correlation_id,
        "repository": repository,
        "base_branch": base_branch,
        "decisions": [
            {
                "kind": "issue",
                "number": issue_number,
                "route": LOCAL_CODEX_ROUTE,
                "status": "dispatched",
            }
        ],
    }


def local_codex_decisions(report: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in report.get("decisions") or []:
        if not isinstance(item, dict):
            continue
        if item.get("kind") != "issue":
            continue
        if item.get("route") != LOCAL_CODEX_ROUTE:
            continue
        if item.get("status") not in ELIGIBLE_STATUSES:
            continue
        if int(item.get("number") or 0) < 1:
            continue
        result.append(item)
    return result


def validate_base_sha(value: str) -> str:
    normalized = value.strip().lower()
    if not SHA40.fullmatch(normalized):
        raise BridgeError("base_sha_invalid")
    return normalized


def validate_pool_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
        raise BridgeError("worker_pool_url_not_loopback")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise BridgeError("worker_pool_url_invalid")
    if parsed.path not in {"", "/"}:
        raise BridgeError("worker_pool_url_invalid")
    return raw


def read_token(path: Path | None) -> str:
    if path is None:
        raise BridgeError("worker_pool_token_file_not_configured")
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise BridgeError("worker_pool_token_unavailable") from exc
    if not token:
        raise BridgeError("worker_pool_token_empty")
    return token


def http_request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None,
) -> tuple[int, dict[str, Any]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - loopback URL validated.
            body = response.read().decode("utf-8")
            decoded = json.loads(body) if body else {}
            return int(response.status), decoded if isinstance(decoded, dict) else {}
    except HTTPError as exc:
        raise BridgeError(f"worker_pool_http_{exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise BridgeError("worker_pool_unreachable") from exc
    except json.JSONDecodeError as exc:
        raise BridgeError("worker_pool_invalid_json") from exc


def verify_health(pool_url: str, token: str, request_fn: RequestFn) -> None:
    code, payload = request_fn("GET", f"{pool_url}/health", token, None)
    if code != 200 or payload.get("status") != "healthy":
        raise BridgeError("worker_pool_not_ready")


def _task_id(payload: dict[str, Any]) -> str:
    task = payload.get("task")
    if not isinstance(task, dict) or not str(task.get("task_id") or ""):
        raise BridgeError("worker_pool_task_response_invalid")
    return str(task["task_id"])


def enqueue_local_work(
    report: dict[str, Any],
    *,
    base_sha: str,
    pool_url: str,
    token: str,
    request_fn: RequestFn = http_request,
) -> dict[str, Any]:
    decisions = local_codex_decisions(report)
    if not decisions:
        return {
            "schema_version": "1.0.0",
            "result": "NO_LOCAL_CODEX_WORK",
            "enqueued": 0,
            "items": [],
        }

    base_sha = validate_base_sha(base_sha)
    pool_url = validate_pool_url(pool_url)
    repository = str(report.get("repository") or "").strip()
    base_branch = str(report.get("base_branch") or "").strip()
    parent_correlation = str(report.get("correlation_id") or "").strip()
    if "/" not in repository or not base_branch or not parent_correlation:
        raise BridgeError("orchestrator_identity_invalid")

    verify_health(pool_url, token, request_fn)
    evidence: list[dict[str, Any]] = []
    for item in decisions:
        issue_number = int(item["number"])
        request_id = local_codex_request_id(repository, issue_number, base_branch)
        correlation_id = f"{parent_correlation}-issue-{issue_number}"[:128]
        body = {
            "repository": repository,
            "issue_number": issue_number,
            "request_id": request_id,
            "correlation_id": correlation_id,
            "priority": 10,
            "base_sha": base_sha,
            "max_attempts": 3,
        }

        first_code, first = request_fn("POST", f"{pool_url}/v1/tasks", token, body)
        if first_code not in {200, 201}:
            raise BridgeError("worker_pool_enqueue_failed")
        task_id = _task_id(first)

        replay_code, replay = request_fn("POST", f"{pool_url}/v1/tasks", token, body)
        if replay_code != 200 or replay.get("created") is not False:
            raise BridgeError("worker_pool_replay_not_idempotent")
        if _task_id(replay) != task_id:
            raise BridgeError("worker_pool_replay_task_mismatch")

        read_code, readback = request_fn("GET", f"{pool_url}/v1/tasks/{task_id}", token, None)
        if read_code != 200:
            raise BridgeError("worker_pool_readback_failed")
        expected = {
            "task_id": task_id,
            "repository": repository,
            "issue_number": issue_number,
            "request_id": request_id,
            "base_sha": base_sha,
        }
        if any(readback.get(key) != value for key, value in expected.items()):
            raise BridgeError("worker_pool_readback_mismatch")
        if "lease_token" in readback:
            raise BridgeError("worker_pool_readback_leaked_lease")

        task = first["task"]
        evidence.append(
            {
                "issue_number": issue_number,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "branch": task.get("branch"),
                "workspace_key": task.get("workspace_key"),
                "state": readback.get("state"),
                "base_sha": base_sha,
                "created": first.get("created") is True,
                "replay_created": replay.get("created"),
                "independent_readback": True,
            }
        )

    return {
        "schema_version": "1.0.0",
        "result": "WORKER_POOL_ENQUEUED",
        "repository": repository,
        "base_sha": base_sha,
        "orchestrator_correlation_id": parent_correlation,
        "enqueued": len(evidence),
        "items": evidence,
    }


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Handoff local Codex para o Worker Pool governado")
    source = root.add_mutually_exclusive_group(required=True)
    source.add_argument("--report-json", type=Path)
    source.add_argument("--issue-number", type=int)
    root.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", ""))
    root.add_argument("--base-branch", default="main")
    root.add_argument("--correlation-id", default=os.getenv("GITHUB_RUN_ID", "worker-pool-handoff"))
    root.add_argument("--base-sha", default=os.getenv("GITHUB_SHA", ""))
    root.add_argument("--pool-url", default=os.getenv("CODEX_WORKER_POOL_URL", "http://127.0.0.1:8097"))
    root.add_argument("--token-file", type=Path)
    root.add_argument("--output", type=Path, default=Path("artifacts/pending-development-worker-pool/evidence.json"))
    root.add_argument("--probe-only", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.report_json is not None:
            report = load_report(args.report_json)
        else:
            report = direct_report(
                args.repository,
                int(args.issue_number or 0),
                args.base_branch,
                args.correlation_id,
            )
        if args.probe_only:
            print("true" if local_codex_decisions(report) else "false")
            return 0

        token_path = args.token_file
        if token_path is None:
            configured = (
                os.getenv("CODEX_WORKER_POOL_API_TOKEN_FILE", "").strip()
                or os.getenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", "").strip()
            )
            token_path = Path(configured) if configured else None
        token = read_token(token_path)
        result = enqueue_local_work(
            report,
            base_sha=args.base_sha,
            pool_url=args.pool_url,
            token=token,
        )
        write_evidence(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except BridgeError as exc:
        blocked = {
            "schema_version": "1.0.0",
            "result": "WORKER_POOL_BRIDGE_BLOCKED",
            "reason": str(exc),
        }
        write_evidence(args.output, blocked)
        print(json.dumps(blocked, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
