#!/usr/bin/env python3
"""Reconcilia o runtime Teams DEV persistente do PC24x7 com um SHA governado."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from scripts import provision_pc24x7_teams_bot_runtime as provision

CONFIRMATION = "RECONCILE-PC24X7-TEAMS-DEV"
EXPECTED_HOST = "DESKTOP-PDQK954"
EXPECTED_PROJECT = "wt-pc24x7-piloto"
EXPECTED_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
DEV_API_PORT = "8210"
ADMIN_OVERRIDE_NAME = "docker-compose.admin-dev.override.yml"
TEAMS_OVERRIDE_REL = Path("config/pc24x7-teams-bot-runtime.override.yml")


class ReconcileError(RuntimeError):
    pass


def _tool(name: str) -> str:
    for candidate in (name, f"{name}.exe", f"{name}.cmd", f"{name}.bat"):
        found = shutil.which(candidate)
        if found:
            return found
    raise ReconcileError(f"tool_missing:{name}")


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 180,
    sensitive: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )
    if check and result.returncode != 0:
        if sensitive:
            raise ReconcileError(
                f"sensitive_command_failed:{Path(args[0]).name}:exit_{result.returncode}"
            )
        detail = (result.stderr or result.stdout or "").strip().replace("\n", " ")
        raise ReconcileError(
            f"command_failed:{Path(args[0]).name}:exit_{result.returncode}:{detail[:300]}"
        )
    return result


def _windows_path(raw: str) -> Path:
    value = raw.strip()
    lowered = value.lower()
    for prefix in ("/run/desktop/mnt/host/", "/host_mnt/"):
        if lowered.startswith(prefix):
            tail = value[len(prefix):]
            parts = tail.split("/", 1)
            if len(parts) == 2 and len(parts[0]) == 1:
                return Path(f"{parts[0].upper()}:/{parts[1]}")
    return Path(value)


def _require_host() -> None:
    if os.name != "nt":
        raise ReconcileError("windows_required")
    if socket.gethostname().casefold() != EXPECTED_HOST.casefold():
        raise ReconcileError("host_not_allowed")


def _inspect_container(container_id: str, cwd: Path) -> dict[str, Any]:
    raw = _run(
        [_tool("docker"), "inspect", container_id],
        cwd=cwd,
        timeout=60,
    ).stdout
    payload = json.loads(raw)
    if not isinstance(payload, list) or len(payload) != 1:
        raise ReconcileError("docker_inspect_invalid")
    return payload[0]


def _discover_runtime() -> tuple[Path, Path, str]:
    cwd = Path.cwd()
    result = _run(
        [
            _tool("docker"),
            "ps",
            "--filter",
            f"publish={DEV_API_PORT}",
            "--format",
            "{{.ID}}",
        ],
        cwd=cwd,
        timeout=60,
    )
    ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(ids) != 1:
        raise ReconcileError("dev_api_8210_not_unique")

    item = _inspect_container(ids[0], cwd)
    labels = (item.get("Config") or {}).get("Labels") or {}
    project = str(labels.get("com.docker.compose.project") or "").strip()
    service = str(labels.get("com.docker.compose.service") or "").strip()
    if project != EXPECTED_PROJECT or service != "api":
        raise ReconcileError("non_dev_runtime_target_blocked")

    working_raw = str(labels.get("com.docker.compose.project.working_dir") or "").strip()
    if not working_raw:
        raise ReconcileError("compose_working_dir_missing")
    runtime_root = _windows_path(working_raw).resolve()
    if not runtime_root.is_dir():
        raise ReconcileError("compose_working_dir_not_found")

    config_raw = str(labels.get("com.docker.compose.project.config_files") or "")
    candidates: list[Path] = []
    for raw in config_raw.split(","):
        value = raw.strip()
        if not value:
            continue
        path = _windows_path(value)
        if not path.is_absolute():
            path = runtime_root / path
        if path.name.casefold() == ADMIN_OVERRIDE_NAME.casefold() and path.is_file():
            candidates.append(path.resolve())
    if len(candidates) != 1:
        raise ReconcileError("admin_override_not_unique")
    return runtime_root, candidates[0], project


def _origin_is_expected(raw: str) -> bool:
    value = raw.strip().replace("\\", "/").rstrip("/")
    value = re.sub(r"\.git$", "", value, flags=re.IGNORECASE).casefold()
    expected = EXPECTED_REPOSITORY.casefold()
    return value in {
        f"https://github.com/{expected}",
        f"git@github.com:{expected}",
        f"ssh://git@github.com/{expected}",
    }


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run([_tool("git"), "-C", str(repo), *args], cwd=repo, timeout=180, check=check)


def _sync_runtime_repo(runtime_root: Path, expected_sha: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", expected_sha):
        raise ReconcileError("expected_sha_invalid")

    origin = _git(runtime_root, "remote", "get-url", "origin").stdout.strip()
    if not _origin_is_expected(origin):
        raise ReconcileError("runtime_origin_mismatch")

    tracked = _git(
        runtime_root,
        "status",
        "--porcelain",
        "--untracked-files=no",
    ).stdout.strip()
    if tracked:
        raise ReconcileError("runtime_tracked_tree_dirty")

    before = _git(runtime_root, "rev-parse", "HEAD").stdout.strip().lower()
    _git(runtime_root, "fetch", "--prune", "origin", "main")
    remote_main = _git(runtime_root, "rev-parse", "origin/main").stdout.strip().lower()
    expected = expected_sha.lower()

    expected_on_main = _git(
        runtime_root,
        "merge-base",
        "--is-ancestor",
        expected,
        remote_main,
        check=False,
    )
    if expected_on_main.returncode != 0:
        raise ReconcileError("expected_sha_not_on_origin_main")

    changed = False
    if before != expected:
        can_fast_forward = _git(
            runtime_root,
            "merge-base",
            "--is-ancestor",
            before,
            expected,
            check=False,
        )
        if can_fast_forward.returncode != 0:
            raise ReconcileError("runtime_not_fast_forwardable")
        _git(runtime_root, "merge", "--ff-only", expected)
        changed = True

    after = _git(runtime_root, "rev-parse", "HEAD").stdout.strip().lower()
    if after != expected:
        raise ReconcileError("runtime_head_mismatch_after_sync")

    tracked_after = _git(
        runtime_root,
        "status",
        "--porcelain",
        "--untracked-files=no",
    ).stdout.strip()
    if tracked_after:
        raise ReconcileError("runtime_tracked_tree_dirty_after_sync")

    return {
        "before_sha": before,
        "after_sha": after,
        "origin_main_sha": remote_main,
        "fast_forward_performed": changed,
    }


def _parse_last_json(stdout: str, label: str) -> dict[str, Any]:
    for raw in reversed([line.strip() for line in stdout.splitlines() if line.strip()]):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ReconcileError(f"{label}_json_missing")


def _recreate_api(
    runtime_root: Path,
    admin_override: Path,
    expected_sha: str,
    vault_name: str,
    expected_tenant_id: str,
) -> dict[str, Any]:
    teams_override = (runtime_root / TEAMS_OVERRIDE_REL).resolve()
    if not teams_override.is_file():
        raise ReconcileError("teams_override_missing")

    app_id, bot_secret = provision._load_existing_bot_secret(
        vault_name,
        expected_tenant_id,
    )
    child_env = os.environ.copy()
    child_env["TEAMS_BOT_APP_ID"] = app_id
    child_env["TEAMS_BOT_APP_TENANT_ID"] = expected_tenant_id
    child_env["TEAMS_BOT_SECRET"] = bot_secret
    try:
        result = _run(
            [
                sys.executable,
                str(runtime_root / "scripts" / "recreate_cofre_dev_pc24x7.py"),
                "--repo-root",
                str(runtime_root),
                "--expected-sha",
                expected_sha,
                "--admin-override",
                str(admin_override),
                "--teams-override",
                str(teams_override),
                "--health-timeout",
                "240",
            ],
            cwd=runtime_root,
            env=child_env,
            timeout=720,
            sensitive=True,
        )
        return _parse_last_json(result.stdout, "recreate")
    finally:
        child_env["TEAMS_BOT_SECRET"] = ""
        bot_secret = ""


def _probe_json(path: str, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{DEV_API_PORT}{path}",
        headers={"Accept": "application/json", "User-Agent": "reqsys-pc24x7-reconcile/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if int(response.status) != 200:
                raise ReconcileError(f"runtime_probe_http_{response.status}")
            payload = json.loads(response.read(262_144).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ReconcileError("runtime_probe_failed") from exc
    if not isinstance(payload, dict):
        raise ReconcileError("runtime_probe_payload_invalid")
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise ReconcileError("runtime_probe_data_invalid")
    return data


def _verify_runtime(expected_sha: str) -> dict[str, Any]:
    deadline = time.monotonic() + 90
    last_build = ""
    while time.monotonic() < deadline:
        try:
            build = _probe_json("/api/runtime/build-info")
            last_build = str(build.get("build_sha") or "").strip().lower()
            health = _probe_json("/api/runtime/health")
            if last_build == expected_sha.lower():
                return {
                    "build_sha": last_build,
                    "health_status": str(health.get("status") or "unknown"),
                }
        except ReconcileError:
            pass
        time.sleep(2)
    raise ReconcileError(f"runtime_same_sha_timeout:{last_build or 'missing'}")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise ReconcileError(f"confirmation_required:{CONFIRMATION}")
    if args.environment != "dev":
        raise ReconcileError("environment_must_be_dev")
    _require_host()

    runtime_root, admin_override, project = _discover_runtime()
    sync = _sync_runtime_repo(runtime_root, args.expected_sha)
    recreate = _recreate_api(
        runtime_root,
        admin_override,
        args.expected_sha,
        args.vault_name,
        args.expected_tenant_id,
    )
    runtime = _verify_runtime(args.expected_sha)

    evidence = {
        "schema_version": "1.0.0",
        "status": "ready",
        "environment": "dev",
        "host": EXPECTED_HOST,
        "project": project,
        "correlation_id": args.correlation_id,
        "expected_sha": args.expected_sha.lower(),
        "runtime_root_discovered_from_compose": True,
        "admin_override_reused": True,
        "teams_override_reused": True,
        "sync": sync,
        "recreate": recreate,
        "runtime": runtime,
        "secret_value_exposed": False,
        "production_touched": False,
    }
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--environment", default="dev")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--vault-name", required=True)
    parser.add_argument("--expected-tenant-id", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        execute(args)
        return 0
    except Exception as exc:
        failure = {
            "schema_version": "1.0.0",
            "status": "blocked",
            "environment": "dev",
            "correlation_id": args.correlation_id,
            "expected_sha": args.expected_sha,
            "reason": type(exc).__name__,
            "detail": str(exc)[:300],
            "secret_value_exposed": False,
            "production_touched": False,
        }
        args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.write_text(
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
