#!/usr/bin/env python3
"""Reconcilia o runtime DEV do Codex Worker Pool no PC24x7 de forma fail-closed."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
SERVICE = "codex-worker-pool"
COMPOSE_FILE = "docker-compose.pc24x7-codex-worker-pool.yml"
TOKEN_DESTINATION = "/run/secrets/codex_worker_pool_api_token"
HOST_IP = "127.0.0.1"
HOST_PORT = "8097"
CONTAINER_PORT = "8097/tcp"
CONFIRM = "RECONCILE-CODEX-WORKER-POOL-DEV"
RULES_COMMIT_URL = "https://api.github.com/repos/ericson-j-santos/chatgpt-operational-rules/commits/main"


class ReconcileError(RuntimeError):
    pass


def _run(argv: list[str], *, env: dict[str, str] | None = None, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=env,
    )


def _docker() -> str:
    executable = shutil.which("docker")
    if not executable:
        raise ReconcileError("docker_not_found")
    return executable


def require_host() -> str:
    if os.name != "nt":
        raise ReconcileError("windows_required")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise ReconcileError("unexpected_host")
    return host


def _service_container_ids(*, all_containers: bool) -> list[str]:
    argv = [_docker(), "ps"]
    if all_containers:
        argv.append("-a")
    argv += ["--filter", f"label=com.docker.compose.service={SERVICE}", "--format", "{{.ID}}"]
    completed = _run(argv, timeout=30)
    if completed.returncode != 0:
        raise ReconcileError("docker_ps_failed")
    return list(dict.fromkeys(line.strip() for line in completed.stdout.splitlines() if line.strip()))


def _inspect(container_ids: list[str]) -> list[dict[str, Any]]:
    if not container_ids:
        return []
    completed = _run([_docker(), "inspect", *container_ids], timeout=30)
    if completed.returncode != 0:
        raise ReconcileError("docker_inspect_failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ReconcileError("docker_inspect_invalid") from exc
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ReconcileError("docker_inspect_invalid")
    return payload


def _canonical_host_binding(container: dict[str, Any]) -> bool:
    host_config = container.get("HostConfig") or {}
    port_bindings = host_config.get("PortBindings") or {}
    bindings = port_bindings.get(CONTAINER_PORT) or []
    return any(
        isinstance(binding, dict)
        and str(binding.get("HostIp") or "") == HOST_IP
        and str(binding.get("HostPort") or "") == HOST_PORT
        for binding in bindings
    )


def _canonical_compose_identity(container: dict[str, Any]) -> bool:
    labels = (container.get("Config") or {}).get("Labels") or {}
    if labels.get("com.docker.compose.service") != SERVICE:
        return False
    config_files = str(labels.get("com.docker.compose.project.config_files") or "")
    normalized = config_files.replace("\\", "/").casefold()
    return COMPOSE_FILE.casefold() in normalized


def _canonical_token_mount(container: dict[str, Any]) -> str | None:
    matches = [
        str(mount.get("Source") or "").strip()
        for mount in container.get("Mounts") or []
        if isinstance(mount, dict)
        and mount.get("Type") == "bind"
        and mount.get("Destination") == TOKEN_DESTINATION
        and str(mount.get("Source") or "").strip()
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def _created_at(container: dict[str, Any]) -> datetime:
    raw = str(container.get("Created") or "").strip()
    if not raw:
        raise ReconcileError("worker_pool_container_created_missing")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReconcileError("worker_pool_container_created_invalid") from exc
    if value.tzinfo is None:
        raise ReconcileError("worker_pool_container_created_invalid")
    return value



def _host_path_candidates(source: str) -> list[Path]:
    raw = source.strip()
    if not raw:
        return []
    candidates = [Path(raw)]
    normalized = raw.replace("\\", "/")
    for prefix in ("/run/desktop/mnt/host/", "/host_mnt/", "/mnt/"):
        if not normalized.casefold().startswith(prefix.casefold()):
            continue
        remainder = normalized[len(prefix):]
        drive, separator, tail = remainder.partition("/")
        if len(drive) != 1 or not drive.isalpha():
            continue
        windows = f"{drive.upper()}:\\\\{tail.replace('/', '\\\\')}" if separator else f"{drive.upper()}:\\\\"
        candidates.append(Path(windows))
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _existing_host_path(source: str) -> Path | None:
    for candidate in _host_path_candidates(source):
        if candidate.is_file():
            return candidate
    return None

def discover_token_source() -> tuple[Path, str]:
    configured = os.environ.get("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path, "environment"
        raise ReconcileError("configured_token_file_missing")

    candidates: list[tuple[int, datetime, str]] = []
    for container in _inspect(_service_container_ids(all_containers=True)):
        labels = (container.get("Config") or {}).get("Labels") or {}
        if labels.get("com.docker.compose.service") != SERVICE:
            continue
        source = _canonical_token_mount(container)
        if source is None:
            continue
        host_path = _existing_host_path(source)
        if host_path is None:
            continue
        identity_score = int(_canonical_compose_identity(container)) * 2
        identity_score += int(_canonical_host_binding(container))
        candidates.append((identity_score, _created_at(container), str(host_path)))

    if not candidates:
        raise ReconcileError("worker_pool_token_source_missing")

    best_score = max(score for score, _created, _source in candidates)
    ranked = [
        (created, source)
        for score, created, source in candidates
        if score == best_score
    ]
    newest = max(created for created, _source in ranked)
    newest_sources = {source for created, source in ranked if created == newest}
    if len(newest_sources) != 1:
        raise ReconcileError("worker_pool_latest_token_source_ambiguous")

    path = Path(next(iter(newest_sources)))
    return path, "latest_ranked_canonical_docker_mount_history"


def resolve_rules_sha() -> str:
    request = urllib.request.Request(
        RULES_COMMIT_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ReqSys-Worker-Pool-Reconcile/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    sha = str(payload.get("sha") or "")
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha.casefold()):
        raise ReconcileError("rules_sha_invalid")
    return sha


def _canonical_endpoint_containers() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for container in _inspect(_service_container_ids(all_containers=False)):
        labels = (container.get("Config") or {}).get("Labels") or {}
        state = container.get("State") or {}
        ports = (container.get("NetworkSettings") or {}).get("Ports") or {}
        bindings = ports.get(CONTAINER_PORT) or []
        canonical = [
            binding
            for binding in bindings
            if isinstance(binding, dict)
            and str(binding.get("HostIp") or "") == HOST_IP
            and str(binding.get("HostPort") or "") == HOST_PORT
        ]
        if labels.get("com.docker.compose.service") == SERVICE and state.get("Running") is True and len(canonical) == 1:
            result.append(container)
    return result


def _health_ready(timeout_seconds: int = 90) -> bool:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://{HOST_IP}:{HOST_PORT}/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    payload = json.loads(response.read().decode("utf-8"))
                    if payload.get("status") == "ok":
                        return True
        except Exception:
            pass
        time.sleep(2)
    return False


def reconcile(repo_root: Path) -> dict[str, Any]:
    host = require_host()
    compose = (repo_root / COMPOSE_FILE).resolve()
    if not compose.is_file():
        raise ReconcileError("compose_file_missing")

    token_source, token_source_method = discover_token_source()
    rules_sha = resolve_rules_sha()

    env = os.environ.copy()
    env["CODEX_WORKER_POOL_API_TOKEN_FILE_HOST"] = str(token_source)
    env["CODEX_WORKER_POOL_EXPECTED_RULES_SHA"] = rules_sha
    env["COMPOSE_PROJECT_NAME"] = "reqsys-codex-worker-pool"

    completed = _run(
        [_docker(), "compose", "-f", str(compose), "up", "-d", "--build", "--remove-orphans", SERVICE],
        env=env,
        timeout=600,
    )
    if completed.returncode != 0:
        raise ReconcileError(f"docker_compose_up_failed:{completed.returncode}")

    if not _health_ready():
        raise ReconcileError("worker_pool_health_not_ready")

    endpoints = _canonical_endpoint_containers()
    if len(endpoints) != 1:
        raise ReconcileError("worker_pool_endpoint_container_not_unique")

    return {
        "schema_version": "1.0.0",
        "result": "WORKER_POOL_RUNTIME_RECONCILED",
        "host": host,
        "service": SERVICE,
        "endpoint": f"http://{HOST_IP}:{HOST_PORT}",
        "endpoint_container_unique": True,
        "rules_sha": rules_sha,
        "token_source_method": token_source_method,
        "token_content_read": False,
        "production_touched": False,
        "deploy_executed": False,
        "runtime_reconciled": True,
    }


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    if args.confirm != CONFIRM:
        write_evidence(args.evidence_file, {"result": "WORKER_POOL_RUNTIME_BLOCKED", "reason": "confirmation_invalid"})
        return 2

    try:
        payload = reconcile(args.repo_root.resolve())
        code = 0
    except Exception as exc:
        payload = {
            "schema_version": "1.0.0",
            "result": "WORKER_POOL_RUNTIME_BLOCKED",
            "reason": str(exc)[:300],
            "token_content_read": False,
            "production_touched": False,
            "deploy_executed": False,
            "runtime_reconciled": False,
        }
        code = 4
    write_evidence(args.evidence_file, payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
