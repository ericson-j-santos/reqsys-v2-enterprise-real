#!/usr/bin/env python3
"""Restaura de forma governada o arquivo local de autenticação do Codex Worker Pool DEV."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
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
REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_COMPOSE_FILE = REPO_ROOT / "docker-compose.pc24x7-codex-worker-pool.yml"


class RestoreError(RuntimeError):
    def __init__(self, reason: str, *, diagnostics: dict[str, str] | None = None) -> None:
        super().__init__(reason)
        self.diagnostics = diagnostics or {}


def _docker(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    failure_reason: str = "worker_pool_docker_command_failed",
) -> str:
    try:
        completed = subprocess.run(
            ["docker", *args],
            check=True,
            text=True,
            capture_output=True,
            timeout=60,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        reason = failure_reason
        diagnostics: dict[str, str] = {}
        if failure_reason == "worker_pool_compose_recreate_failed":
            stderr = exc.stderr or ""
            reason = _compose_failure_reason(stderr)
            diagnostics["compose_error_fingerprint"] = hashlib.sha256(
                stderr.encode("utf-8", errors="replace")
            ).hexdigest()
        raise RestoreError(reason, diagnostics=diagnostics) from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RestoreError(failure_reason) from exc
    return completed.stdout


def _compose_failure_reason(stderr: str) -> str:
    normalized = stderr.casefold()
    classifications = (
        (
            "worker_pool_compose_image_unavailable",
            ("no such image", "pull access denied", "unable to get image"),
        ),
        (
            "worker_pool_compose_bind_source_unavailable",
            (
                "bind source path does not exist",
                "invalid mount config",
                "path is not shared",
                "file sharing",
            ),
        ),
        (
            "worker_pool_compose_port_conflict",
            ("port is already allocated", "address already in use"),
        ),
        (
            "worker_pool_compose_configuration_invalid",
            ("required variable", "is missing a value", "invalid interpolation format"),
        ),
        (
            "worker_pool_compose_image_reference_invalid",
            (
                "invalid repository name",
                "invalid reference format",
                "cannot specify 64-byte hexadecimal strings",
            ),
        ),
        (
            "worker_pool_compose_cli_incompatible",
            (
                "unknown flag: --pull",
                "unknown shorthand flag",
                'invalid value "never" for --pull',
                "invalid value 'never' for --pull",
            ),
        ),
    )
    for reason, markers in classifications:
        if any(marker in normalized for marker in markers):
            return reason
    return "worker_pool_compose_recreate_failed"


_COMPOSE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _sanitize_compose_version(value: object) -> str:
    normalized = str(value or "").strip()
    if normalized.lower().startswith("v"):
        normalized = normalized[1:]
    return normalized if _COMPOSE_VERSION_RE.fullmatch(normalized) else "unknown"


def _compose_cli_version() -> str:
    raw = _docker(
        ["compose", "version", "--short"],
        failure_reason="worker_pool_compose_version_unavailable",
    )
    version = _sanitize_compose_version(raw)
    if version == "unknown":
        raise RestoreError("worker_pool_compose_version_invalid")
    return version


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


def _inspect_container(container_id: str) -> dict[str, Any]:
    try:
        payload = json.loads(_docker(["inspect", container_id]))
    except json.JSONDecodeError as exc:
        raise RestoreError("worker_pool_container_inspect_invalid") from exc
    if (
        not isinstance(payload, list)
        or len(payload) != 1
        or not isinstance(payload[0], dict)
    ):
        raise RestoreError("worker_pool_container_inspect_invalid")
    return payload[0]


def _validate_container_auth_contract(container: dict[str, Any]) -> None:
    env_entries = (container.get("Config") or {}).get("Env") or []
    expected = f"CODEX_WORKER_POOL_API_TOKEN_FILE={TOKEN_DESTINATION}"
    if expected not in env_entries:
        raise RestoreError("worker_pool_token_env_mismatch")


def _container_token_matches_host(container_id: str, host_token: str) -> bool:
    script = (
        "from pathlib import Path; import sys; "
        f"sys.stdout.write(Path({TOKEN_DESTINATION!r}).read_text(encoding='utf-8').strip())"
    )
    container_token = _docker(
        ["exec", container_id, "python", "-c", script],
        failure_reason="worker_pool_container_token_read_failed",
    ).strip()
    if not container_token:
        raise RestoreError("worker_pool_container_token_empty")
    return hmac.compare_digest(container_token, host_token)


def _canonical_compose_contract_valid(path: Path) -> bool:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return False
    required_fragments = (
        "codex-worker-pool:",
        '127.0.0.1:8097:8097',
        f"CODEX_WORKER_POOL_API_TOKEN_FILE: {TOKEN_DESTINATION}",
        "CODEX_WORKER_POOL_API_TOKEN_FILE_HOST",
        f":{TOKEN_DESTINATION}:ro",
        "CODEX_WORKER_POOL_EXPECTED_RULES_SHA",
        "codex-worker-pool-state:/data",
        "restart: unless-stopped",
    )
    return all(fragment in raw for fragment in required_fragments)


def _resolve_compose_source(labels: dict[str, Any]) -> tuple[Path, list[Path], bool]:
    working_dir_raw = str(
        labels.get("com.docker.compose.project.working_dir") or ""
    ).strip()
    config_raw = str(
        labels.get("com.docker.compose.project.config_files") or ""
    ).strip()
    configured = [Path(item.strip()) for item in config_raw.split(",") if item.strip()]
    if working_dir_raw and configured:
        working_dir = Path(working_dir_raw)
        if working_dir.is_dir() and all(path.is_file() for path in configured):
            return working_dir, configured, False

    if len(configured) != 1 or configured[0].name != CANONICAL_COMPOSE_FILE.name:
        raise RestoreError("worker_pool_compose_source_unavailable")
    if not CANONICAL_COMPOSE_FILE.is_file() or not _canonical_compose_contract_valid(
        CANONICAL_COMPOSE_FILE
    ):
        raise RestoreError("worker_pool_canonical_compose_invalid")
    return CANONICAL_COMPOSE_FILE.parent, [CANONICAL_COMPOSE_FILE], True


def _running_image_id(container: dict[str, Any]) -> str:
    image_id = str(container.get("Image") or "").strip().lower()
    prefix = "sha256:"
    digest = image_id[len(prefix):] if image_id.startswith(prefix) else ""
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise RestoreError("worker_pool_running_image_invalid")
    return image_id


def _compose_recreate_service(
    container: dict[str, Any],
    token_path: Path,
) -> bool:
    labels = (container.get("Config") or {}).get("Labels") or {}
    project = str(labels.get("com.docker.compose.project") or "").strip()
    if not project:
        raise RestoreError("worker_pool_compose_identity_missing")

    compose_cli_version = _compose_cli_version()
    compose_creator_version = _sanitize_compose_version(
        labels.get("com.docker.compose.version")
    )
    working_dir, config_files, recovered_source = _resolve_compose_source(labels)

    config_env = (container.get("Config") or {}).get("Env") or []
    rules_sha = ""
    for item in config_env:
        if isinstance(item, str) and item.startswith(
            "CODEX_WORKER_POOL_EXPECTED_RULES_SHA="
        ):
            rules_sha = item.split("=", 1)[1].strip()
            break
    if not rules_sha:
        raise RestoreError("worker_pool_expected_rules_sha_not_configured")

    image_id = _running_image_id(container)
    process_env = os.environ.copy()
    process_env["CODEX_WORKER_POOL_API_TOKEN_FILE_HOST"] = str(token_path)
    process_env["CODEX_WORKER_POOL_EXPECTED_RULES_SHA"] = rules_sha

    with tempfile.TemporaryDirectory(prefix="worker-pool-compose-") as temp_dir:
        image_override = Path(temp_dir) / "running-image.override.json"
        image_override.write_text(
            json.dumps(
                {"services": {SERVICE: {"image": image_id}}},
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        args = [
            "compose",
            "--project-name",
            project,
            "--project-directory",
            str(working_dir),
        ]
        for config_file in config_files:
            args.extend(["--file", str(config_file)])
        args.extend(["--file", str(image_override)])
        args.extend(
            [
                "up",
                "-d",
                "--force-recreate",
                "--no-deps",
                "--no-build",
                "--pull",
                "never",
                SERVICE,
            ]
        )
        try:
            _docker(
                args,
                env=process_env,
                failure_reason="worker_pool_compose_recreate_failed",
            )
        except RestoreError as exc:
            diagnostics = dict(exc.diagnostics)
            diagnostics["compose_cli_version"] = compose_cli_version
            diagnostics["compose_creator_version"] = compose_creator_version
            raise RestoreError(str(exc), diagnostics=diagnostics) from exc
    return recovered_source

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
    container = _inspect_container(container_id)
    _validate_container_auth_contract(container)

    token = _read_existing_token(token_path)
    rotated = token is None
    if rotated:
        token = _write_new_token(token_path)

    recreated = False
    bind_mount_resynced = False
    compose_source_recovered = False
    health_status, healthy, reason = _validate_runtime(token)

    if rotated:
        compose_source_recovered = _compose_recreate_service(container, token_path)
        recreated = True
        bind_mount_resynced = True
        health_status = _wait_runtime(token)
    elif not healthy and reason == "worker_pool_token_mismatch_after_restore":
        if _container_token_matches_host(container_id, token):
            raise RestoreError("worker_pool_auth_process_mismatch")
        compose_source_recovered = _compose_recreate_service(container, token_path)
        recreated = True
        bind_mount_resynced = True
        health_status = _wait_runtime(token)
    elif not healthy:
        raise RestoreError(reason or "worker_pool_runtime_not_ready_after_restore")

    _, healthy, final_reason = _validate_runtime(token)
    if not healthy:
        raise RestoreError(final_reason or "worker_pool_authenticated_readback_failed")

    return {
        "schema_version": "1.0.0",
        "result": "WORKER_POOL_TOKEN_RESTORE_PASSED",
        "environment": "dev",
        "token_rotated": rotated,
        "existing_token_reused": not rotated,
        "service_restarted": False,
        "service_recreated": recreated,
        "bind_mount_resynced": bind_mount_resynced,
        "compose_source_recovered": compose_source_recovered,
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
        blocked.update(exc.diagnostics)
        _write_evidence(args.output, blocked)
        print(json.dumps(blocked, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
