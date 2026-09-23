#!/usr/bin/env python3
"""Restaura de forma governada o arquivo local de autenticação do Codex Worker Pool DEV."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SERVICE = "codex-worker-pool"
CONTAINER_PORT = "8097/tcp"
HOST_IP = "127.0.0.1"
HOST_PORT = "8097"
TOKEN_DESTINATION = "/run/secrets/codex_worker_pool_api_token"
HEALTH_URL = "http://127.0.0.1:8097/health"
SNAPSHOT_URL = "http://127.0.0.1:8097/v1/snapshot"
MIN_TOKEN_LENGTH = 32


class RestoreError(RuntimeError):
    pass


def _docker(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["docker", *args],
            check=True,
            text=True,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RestoreError("worker_pool_docker_command_failed") from exc
    return completed.stdout


def _canonical_container_and_token_path() -> tuple[str, Path]:
    ids = [
        line.strip()
        for line in _docker(
            [
                "ps",
                "--filter",
                f"label=com.docker.compose.service={SERVICE}",
                "--format",
                "{{.ID}}",
            ]
        ).splitlines()
        if line.strip()
    ]
    if not ids:
        raise RestoreError("worker_pool_container_missing")

    try:
        payload = json.loads(_docker(["inspect", *ids]))
    except json.JSONDecodeError as exc:
        raise RestoreError("worker_pool_container_inspect_invalid") from exc

    candidates: list[tuple[str, Path]] = []
    for container in payload if isinstance(payload, list) else []:
        if not isinstance(container, dict):
            continue
        labels = (container.get("Config") or {}).get("Labels") or {}
        if labels.get("com.docker.compose.service") != SERVICE:
            continue
        if (container.get("State") or {}).get("Running") is not True:
            continue
        bindings = ((container.get("NetworkSettings") or {}).get("Ports") or {}).get(CONTAINER_PORT) or []
        if not any(
            isinstance(binding, dict)
            and binding.get("HostIp") == HOST_IP
            and binding.get("HostPort") == HOST_PORT
            for binding in bindings
        ):
            continue
        mounts = [
            mount
            for mount in container.get("Mounts") or []
            if isinstance(mount, dict)
            and mount.get("Type") == "bind"
            and mount.get("Destination") == TOKEN_DESTINATION
            and str(mount.get("Source") or "").strip()
        ]
        if len(mounts) != 1:
            continue
        container_id = str(container.get("Id") or "").strip() or ids[0]
        candidates.append((container_id, Path(str(mounts[0]["Source"]))))

    if len(candidates) != 1:
        raise RestoreError("worker_pool_endpoint_container_not_unique")
    return candidates[0]


def _read_existing_token(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise RestoreError("worker_pool_token_path_not_file")
    try:
        token = path.read_text(encoding="utf-8").strip()
    except PermissionError as exc:
        raise RestoreError("worker_pool_token_permission_denied") from exc
    except OSError as exc:
        raise RestoreError("worker_pool_token_unavailable") from exc
    if not token:
        return None
    if len(token) < MIN_TOKEN_LENGTH:
        raise RestoreError("worker_pool_token_too_short")
    return token


def _ensure_token_parent(parent: Path) -> None:
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RestoreError("worker_pool_token_parent_create_failed") from exc
    if not parent.is_dir():
        raise RestoreError("worker_pool_token_parent_unusable")


def _write_new_token(path: Path) -> str:
    parent = path.parent
    _ensure_token_parent(parent)
    token = secrets.token_urlsafe(48)
    if len(token) < MIN_TOKEN_LENGTH:
        raise RestoreError("worker_pool_generated_token_invalid")

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=".worker-pool-auth-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(token + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
        os.chmod(path, 0o600)
    except OSError as exc:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise RestoreError("worker_pool_token_write_failed") from exc
    return token


def _request(url: str, token: str | None = None) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, method="GET", headers=headers)
    try:
        with urlopen(request, timeout=3) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        return exc.code, payload if isinstance(payload, dict) else {}
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        return 0, {}


def _runtime_failure_reason(
    health_status: int,
    health: dict[str, Any],
    snapshot_status: int,
) -> str:
    if health_status == 0:
        return "worker_pool_health_unreachable"
    if health_status in {200, 503}:
        if health.get("auth_configured") is False:
            return "worker_pool_auth_file_not_visible_in_container"
        if health.get("expected_rules_sha_configured") is False:
            return "worker_pool_expected_rules_sha_not_configured"
    if snapshot_status == 401:
        return "worker_pool_token_mismatch_after_restore"
    if snapshot_status == 503:
        return "worker_pool_auth_file_not_visible_in_container"
    if snapshot_status == 0:
        return "worker_pool_authenticated_endpoint_unreachable"
    return "worker_pool_runtime_not_ready_after_restore"


def _validate_runtime(token: str) -> tuple[int, bool, str]:
    health_status, health = _request(HEALTH_URL)
    snapshot_status, _snapshot = _request(SNAPSHOT_URL, token)
    healthy = (
        health_status == 200
        and health.get("status") == "healthy"
        and health.get("auth_configured") is True
        and health.get("expected_rules_sha_configured") is True
        and snapshot_status == 200
    )
    reason = "" if healthy else _runtime_failure_reason(health_status, health, snapshot_status)
    return health_status, healthy, reason


def _wait_runtime(token: str, attempts: int = 12) -> int:
    last_status = 0
    last_reason = "worker_pool_runtime_not_ready_after_restore"
    for _ in range(attempts):
        last_status, healthy, last_reason = _validate_runtime(token)
        if healthy:
            return last_status
        time.sleep(2)
    raise RestoreError(last_reason)


def restore() -> dict[str, Any]:
    container_id, token_path = _canonical_container_and_token_path()
    token = _read_existing_token(token_path)
    rotated = token is None
    if rotated:
        token = _write_new_token(token_path)

    restarted = False
    health_status, healthy, _reason = _validate_runtime(token)
    if rotated or not healthy:
        _docker(["restart", container_id])
        restarted = True
        health_status = _wait_runtime(token)

    _, healthy, final_reason = _validate_runtime(token)
    if not healthy:
        raise RestoreError(final_reason or "worker_pool_authenticated_readback_failed")

    return {
        "schema_version": "1.0.0",
        "result": "WORKER_POOL_TOKEN_RESTORE_PASSED",
        "environment": "dev",
        "token_rotated": rotated,
        "existing_token_reused": not rotated,
        "service_restarted": restarted,
        "health_http_status": health_status,
        "authenticated_readback": True,
        "secret_value_exposed": False,
        "production_touched": False,
        "deploy_executed": False,
    }


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restaura autenticação local do Worker Pool DEV")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/codex-worker-pool-token-restore-dev/evidence.json"),
    )
    args = parser.parse_args()
    try:
        result = restore()
        _write_evidence(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except RestoreError as exc:
        blocked = {
            "schema_version": "1.0.0",
            "result": "WORKER_POOL_TOKEN_RESTORE_BLOCKED",
            "reason": str(exc),
            "secret_value_exposed": False,
            "production_touched": False,
            "deploy_executed": False,
        }
        _write_evidence(args.output, blocked)
        print(json.dumps(blocked, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
