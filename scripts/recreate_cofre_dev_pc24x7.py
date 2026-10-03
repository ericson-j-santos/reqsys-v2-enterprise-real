#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_PROJECT = "wt-pc24x7-piloto"
DEFAULT_CONTAINER = "wt-pc24x7-piloto-api-1"
DEFAULT_SECRET_FILE = Path(r"C:\ProgramData\ReqSys\secrets\cofre-keyring-passphrase.txt")


class RecreateError(RuntimeError):
    pass


def run(args: list[str], *, cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise RecreateError(f"command_failed:{args[0]}:exit_{completed.returncode}")
    return completed


def git_head(repo_root: Path) -> str:
    return run(["git", "rev-parse", "HEAD"], cwd=repo_root, timeout=30).stdout.strip()


def inspect_container(container: str, *, cwd: Path) -> dict:
    payload = json.loads(run(["docker", "inspect", container], cwd=cwd, timeout=60).stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise RecreateError("docker_inspect_invalid")
    return payload[0]


def wait_healthy(container: str, *, cwd: Path, timeout_seconds: int = 180) -> str:
    deadline = time.monotonic() + timeout_seconds
    last = "unknown"
    while time.monotonic() < deadline:
        item = inspect_container(container, cwd=cwd)
        state = item.get("State") or {}
        health = state.get("Health") or {}
        last = str(health.get("Status") or state.get("Status") or "unknown").lower()
        if last == "healthy":
            return last
        time.sleep(2)
    raise RecreateError(f"container_health_timeout:{last}")


def build_files(repo_root: Path, admin_override: Path, teams_override: Path, sha_override: Path) -> list[Path]:
    return [
        repo_root / "docker-compose.yml",
        repo_root / "docker-compose.dev.yml",
        admin_override,
        teams_override,
        repo_root / "docker-compose.pc24x7-cofre.yml",
        sha_override,
    ]


def compose_args(project: str, files: list[Path]) -> list[str]:
    args = ["docker", "compose", "-p", project]
    for path in files:
        args.extend(["-f", str(path)])
    return args


def execute(args: argparse.Namespace) -> dict:
    repo_root = args.repo_root.resolve()
    if git_head(repo_root) != args.expected_sha:
        raise RecreateError("git_head_mismatch")
    if not args.secret_file.is_file():
        raise RecreateError("cofre_secret_file_missing")
    if args.project != DEFAULT_PROJECT or args.container != DEFAULT_CONTAINER:
        raise RecreateError("non_dev_runtime_target_blocked")
    if not args.admin_override.is_file() or not args.teams_override.is_file():
        raise RecreateError("required_runtime_override_missing")

    temp_dir = repo_root / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    sha_override = temp_dir / "cofre-runtime-sha.override.yml"
    sha_override.write_text(
        "services:\n"
        "  api:\n"
        "    environment:\n"
        f'      GITHUB_SHA: "{args.expected_sha}"\n',
        encoding="utf-8",
    )

    files = build_files(repo_root, args.admin_override.resolve(), args.teams_override.resolve(), sha_override)
    base = compose_args(args.project, files)

    run([*base, "config"], cwd=repo_root, timeout=120)
    run(
        [*base, "up", "-d", "--no-deps", "--build", "--force-recreate", "api"],
        cwd=repo_root,
        timeout=600,
    )
    health = wait_healthy(args.container, cwd=repo_root, timeout_seconds=args.health_timeout)

    item = inspect_container(args.container, cwd=repo_root)
    labels = (item.get("Config") or {}).get("Labels") or {}
    env_items = (item.get("Config") or {}).get("Env") or []
    env_map = dict(entry.split("=", 1) for entry in env_items if "=" in entry)
    mounts = item.get("Mounts") or []

    secret_mount = [
        m for m in mounts
        if m.get("Destination") == "/run/secrets/cofre_keyring_passphrase"
    ]
    data_mount = [m for m in mounts if m.get("Destination") == "/data"]
    backend_mount = [m for m in mounts if m.get("Destination") == "/app"]

    if env_map.get("GITHUB_SHA") != args.expected_sha:
        raise RecreateError("runtime_sha_mismatch")
    if labels.get("com.docker.compose.project") != args.project:
        raise RecreateError("compose_project_mismatch")
    if labels.get("com.docker.compose.service") != "api":
        raise RecreateError("compose_service_mismatch")
    if not secret_mount or secret_mount[0].get("RW") is not False:
        raise RecreateError("secret_mount_not_read_only")
    if not data_mount or data_mount[0].get("Type") != "volume" or data_mount[0].get("RW") is not True:
        raise RecreateError("persistent_data_mount_missing")
    expected_backend = str((repo_root / "backend").resolve()).replace("\\", "/").lower()
    actual_backend = str((backend_mount[0].get("Source") if backend_mount else "")).replace("\\", "/").lower()
    if not actual_backend.endswith(expected_backend.replace("c:/", "/run/desktop/mnt/host/c/")) and expected_backend not in actual_backend:
        raise RecreateError("backend_bind_not_current_worktree")

    return {
        "ok": True,
        "environment": "dev",
        "project": args.project,
        "service": "api",
        "container": args.container,
        "runtime_sha": args.expected_sha,
        "health": health,
        "secret_file_exists": True,
        "secret_value_observed": False,
        "secret_mount_read_only": True,
        "data_volume_persistent": True,
        "backend_bound_to_current_worktree": True,
        "production_touched": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild/recreate governado da API DEV PC24x7 com Cofre")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET_FILE)
    parser.add_argument("--admin-override", type=Path, required=True)
    parser.add_argument("--teams-override", type=Path, required=True)
    parser.add_argument("--health-timeout", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": str(exc),
            "secret_value_observed": False,
            "production_touched": False,
        }, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
