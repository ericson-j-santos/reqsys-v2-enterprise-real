#!/usr/bin/env python3
"""Collect bounded DEV Docker metadata without deployment or credential access."""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import stat
import subprocess
from pathlib import Path

HOST = "DESKTOP-PDQK954"
API_PORT = "8210"
DOCKER_ENDPOINT = "npipe:////./pipe/dockerDesktopLinuxEngine"
LOCAL_DOCKER_CONTEXT_ENDPOINTS = frozenset({
    DOCKER_ENDPOINT,
    "npipe:////./pipe/docker_engine",
})
SERVICES = frozenset({"api", "frontend", "nginx"})
# Match the legacy reconciler's fixed DEV surface; never guess from "healthy".
PROJECTS = frozenset({
    "reqsys-dev", "wt-pc24x7-piloto", "wt-pc24x7-public-dev-governed",
})
INSPECT_FORMAT = (
    '{"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
    '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
    '"state":{{json .State.Status}},"exit_code":{{json .State.ExitCode}},'
    '"oom_killed":{{json .State.OOMKilled}},"restart_count":{{json .RestartCount}},'
    '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}}}'
)


class DiagnosticError(RuntimeError):
    """Only fixed, non-sensitive error codes may leave this module."""


def _verify_docker_target() -> None:
    if any(os.environ.get(key) for key in ("DOCKER_HOST", "DOCKER_CONTEXT")):
        raise DiagnosticError("docker_target_override_blocked")
    try:
        result = subprocess.run(
            ["docker", "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10, check=False, shell=False,
        )
        if result.returncode != 0 or len(result.stdout) > 512:
            raise DiagnosticError("docker_context_unavailable")
        endpoint = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise DiagnosticError("docker_context_unavailable") from None
    # Docker Desktop for Windows can keep the local `default` context active
    # while exposing the Linux engine through its dedicated named pipe.  Both
    # context endpoints are local-only; every inventory command below remains
    # explicitly pinned to DOCKER_ENDPOINT.
    if endpoint not in LOCAL_DOCKER_CONTEXT_ENDPOINTS:
        raise DiagnosticError("docker_context_not_local_dev")


def _capture(args: list[str]) -> str:
    if any(os.environ.get(key) for key in ("DOCKER_HOST", "DOCKER_CONTEXT")):
        raise DiagnosticError("docker_target_override_blocked")
    try:
        result = subprocess.run(
            ["docker", "--host", DOCKER_ENDPOINT, *args],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20, check=False, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise DiagnosticError("docker_read_unavailable") from None
    if result.returncode != 0:
        raise DiagnosticError("docker_read_failed") from None
    output = result.stdout
    if len(output) > 131072:
        raise DiagnosticError("docker_read_too_large")
    return output


def _ids(raw: str) -> list[str]:
    items = raw.split()
    if len(items) > 10 or any(re.fullmatch(r"[0-9a-f]{12,64}", item) is None for item in items):
        raise DiagnosticError("container_inventory_invalid")
    return items


def _inspect(container_id: str) -> dict:
    try:
        item = json.loads(_capture(["inspect", "--format", INSPECT_FORMAT, container_id]))
    except (TypeError, ValueError):
        raise DiagnosticError("container_metadata_invalid") from None
    if not isinstance(item, dict):
        raise DiagnosticError("container_metadata_invalid")
    if not isinstance(item.get("project"), str) or not isinstance(item.get("service"), str):
        raise DiagnosticError("container_metadata_invalid")
    if item["project"] not in PROJECTS or item["service"] not in SERVICES:
        raise DiagnosticError("non_dev_or_unexpected_target")
    state = item.get("state")
    health = item.get("health")
    if not isinstance(state, str) or state not in {"created", "running", "paused", "restarting", "removing", "exited", "dead"}:
        raise DiagnosticError("container_state_invalid")
    if "health" not in item or (health is not None and not isinstance(health, str)):
        raise DiagnosticError("container_health_invalid")
    if health not in {None, "starting", "healthy", "unhealthy"}:
        raise DiagnosticError("container_health_invalid")
    for field in ("exit_code", "restart_count"):
        if type(item.get(field)) is not int or item[field] < 0:
            raise DiagnosticError("container_counters_invalid")
    if type(item.get("oom_killed")) is not bool:
        raise DiagnosticError("container_oom_flag_invalid")
    # Keep only allowlisted scalars; ignore any extra input fields.
    return {key: item[key] for key in (
        "project", "service", "state", "exit_code", "oom_killed", "restart_count", "health"
    )}


def diagnose(environment: str, expected_sha: str) -> dict:
    if environment != "dev":
        raise DiagnosticError("environment_must_be_dev")
    if re.fullmatch(r"[0-9a-f]{40}", expected_sha) is None:
        raise DiagnosticError("expected_sha_invalid")
    if os.name != "nt" or socket.gethostname().casefold() != HOST.casefold():
        raise DiagnosticError("host_not_allowed")
    _verify_docker_target()
    candidates = _ids(_capture(["ps", "--filter", f"publish={API_PORT}", "--format", "{{.ID}}"]))
    if len(candidates) != 1:
        raise DiagnosticError("dev_api_8210_not_unique")
    api = _inspect(candidates[0])
    if api["service"] != "api":
        raise DiagnosticError("dev_api_identity_invalid")
    project = api["project"]
    collected = []
    for service in sorted(SERVICES):
        ids = _ids(_capture([
            "ps", "-a", "--filter", f"label=com.docker.compose.project={project}",
            "--filter", f"label=com.docker.compose.service={service}", "--format", "{{.ID}}",
        ]))
        if len(ids) > 1:
            raise DiagnosticError("dev_service_not_unique")
        if service == "api" and ids != candidates:
            raise DiagnosticError("api_identity_changed")
        if not ids:
            collected.append({"service": service, "present": False})
            continue
        item = _inspect(ids[0])
        if item["project"] != project or item["service"] != service:
            raise DiagnosticError("container_identity_changed")
        collected.append({**item, "present": True})
    return {
        "schema_version": "1.0.0", "status": "diagnostic_collected",
        "environment": "dev", "expected_sha": expected_sha,
        "runtime_sha_verified": False, "runtime_readiness_verified": False,
        "runtime_mutated": False, "production_touched": False,
        "credentials_read": False, "raw_logs_collected": False,
        "containers": collected,
    }


def _reject_links(path: Path) -> None:
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise DiagnosticError("evidence_symlink_blocked")


def _write_evidence(output: Path, result: dict) -> None:
    root = Path.cwd() / "artifacts" / "pc24x7-dev-diagnostic"
    if output.suffix != ".json" or output.name.startswith("."):
        raise DiagnosticError("evidence_filename_invalid")
    absolute = output.absolute()
    if ".." in absolute.parts or not absolute.is_relative_to(root):
        raise DiagnosticError("evidence_path_outside_diagnostic_root")
    if absolute.exists() or absolute.is_symlink():
        raise DiagnosticError("evidence_already_exists")
    _reject_links(absolute)
    absolute.parent.mkdir(parents=True, exist_ok=True)
    _reject_links(absolute)
    with absolute.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True, choices=["dev"])
    parser.add_argument("--expected-sha", required=True)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--stdout-only", action="store_true", help="Emit JSON without creating an evidence file")
    destination.add_argument("--output", type=Path, help="Create a new evidence file (requires an authorized write contract)")
    args = parser.parse_args()
    try:
        result = diagnose(args.environment, args.expected_sha)
        code = 0
    except DiagnosticError as exc:
        result = {"status": "blocked", "reason": str(exc), "runtime_mutated": False}
        code = 1
    if args.output is not None:
        try:
            _write_evidence(args.output, result)
        except (DiagnosticError, OSError):
            print(json.dumps({"status": "blocked", "reason": "evidence_write_blocked"}))
            return 1
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())


