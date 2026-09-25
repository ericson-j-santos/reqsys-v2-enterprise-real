#!/usr/bin/env python3
"""Reconcilia o ReqSys DEV público no PC24x7 com frontend estático e SHA governado."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
EXPECTED_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
DEV_API_PORT = "8210"
DEV_GATEWAY_PORT = "8083"
CONFIRMATION = "RECONCILE-PC24X7-PUBLIC-DEV"
OVERLAY = Path("docker-compose.pc24x7-public-dev.yml")
STATIC_NGINX = Path("infra/nginx/default.pc24x7-public-dev.conf")


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
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 300,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().replace("\n", " ")
        raise ReconcileError(
            f"command_failed:{Path(args[0]).name}:exit_{completed.returncode}:{detail[:240]}"
        )
    return completed


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


def _inspect(container_id: str, cwd: Path) -> dict[str, Any]:
    payload = json.loads(
        _run([_tool("docker"), "inspect", container_id], cwd=cwd, timeout=60).stdout
    )
    if not isinstance(payload, list) or len(payload) != 1:
        raise ReconcileError("docker_inspect_invalid")
    return payload[0]


def _origin_is_expected(raw: str) -> bool:
    value = raw.strip().replace("\\", "/").rstrip("/")
    value = re.sub(r"\.git$", "", value, flags=re.IGNORECASE).casefold()
    expected = EXPECTED_REPOSITORY.casefold()
    return value in {
        f"https://github.com/{expected}",
        f"git@github.com:{expected}",
        f"ssh://git@github.com/{expected}",
    }


def _discover_runtime() -> tuple[str, Path, list[Path], list[Path]]:
    cwd = Path.cwd()
    found = _run(
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
    ids = [line.strip() for line in found.stdout.splitlines() if line.strip()]
    if len(ids) != 1:
        raise ReconcileError("dev_api_8210_not_unique")

    item = _inspect(ids[0], cwd)
    labels = (item.get("Config") or {}).get("Labels") or {}
    project = str(labels.get("com.docker.compose.project") or "").strip()
    service = str(labels.get("com.docker.compose.service") or "").strip()
    if not project or service != "api":
        raise ReconcileError("dev_runtime_identity_invalid")
    if any(token in project.casefold() for token in ("prod", "production", "hml", "stg", "staging")):
        raise ReconcileError("non_dev_runtime_target_blocked")

    working_raw = str(labels.get("com.docker.compose.project.working_dir") or "").strip()
    if not working_raw:
        raise ReconcileError("compose_working_dir_missing")
    runtime_root = _windows_path(working_raw).resolve()
    if not runtime_root.is_dir():
        raise ReconcileError("compose_working_dir_not_found")

    config_files: list[Path] = []
    raw_files = str(labels.get("com.docker.compose.project.config_files") or "")
    for raw in raw_files.split(","):
        value = raw.strip()
        if not value:
            continue
        path = _windows_path(value)
        if not path.is_absolute():
            path = runtime_root / path
        resolved = path.resolve()
        if path.is_file() and resolved not in [p.resolve() for p in config_files]:
            config_files.append(resolved)
    if not config_files:
        for name in ("docker-compose.yml", "docker-compose.dev.yml"):
            path = runtime_root / name
            if path.is_file():
                config_files.append(path.resolve())
    if not config_files:
        raise ReconcileError("compose_config_files_not_found")

    env_files: list[Path] = []
    raw_env = str(labels.get("com.docker.compose.project.environment_file") or "")
    for raw in raw_env.split(","):
        value = raw.strip()
        if not value:
            continue
        path = _windows_path(value)
        if not path.is_absolute():
            path = runtime_root / path
        path = path.resolve()
        if not path.is_file():
            raise ReconcileError("compose_environment_file_missing")
        env_files.append(path)

    return project, runtime_root, config_files, env_files


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(
        [_tool("git"), "-C", str(repo), *args],
        cwd=repo,
        timeout=180,
        check=check,
    )


def _sync_repo(runtime_root: Path, expected_sha: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", expected_sha):
        raise ReconcileError("expected_sha_invalid")
    origin = _git(runtime_root, "remote", "get-url", "origin").stdout.strip()
    if not _origin_is_expected(origin):
        raise ReconcileError("runtime_origin_mismatch")
    tracked = _git(runtime_root, "status", "--porcelain", "--untracked-files=no").stdout.strip()
    if tracked:
        raise ReconcileError("runtime_tracked_tree_dirty")

    before = _git(runtime_root, "rev-parse", "HEAD").stdout.strip().lower()
    _git(runtime_root, "fetch", "--prune", "origin", "main")
    expected = expected_sha.lower()
    remote_main = _git(runtime_root, "rev-parse", "origin/main").stdout.strip().lower()
    on_main = _git(runtime_root, "merge-base", "--is-ancestor", expected, remote_main, check=False)
    if on_main.returncode != 0:
        raise ReconcileError("expected_sha_not_on_origin_main")

    changed = False
    if before != expected:
        ff = _git(runtime_root, "merge-base", "--is-ancestor", before, expected, check=False)
        if ff.returncode != 0:
            raise ReconcileError("runtime_not_fast_forwardable")
        _git(runtime_root, "merge", "--ff-only", expected)
        changed = True

    after = _git(runtime_root, "rev-parse", "HEAD").stdout.strip().lower()
    if after != expected:
        raise ReconcileError("runtime_head_mismatch_after_sync")
    if _git(runtime_root, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise ReconcileError("runtime_tracked_tree_dirty_after_sync")
    return {
        "before_sha": before,
        "after_sha": after,
        "origin_main_sha": remote_main,
        "fast_forward_performed": changed,
    }


def _compose_base(
    runtime_root: Path,
    project: str,
    config_files: list[Path],
    env_files: list[Path],
) -> list[str]:
    command = [
        _tool("docker"),
        "compose",
        "--project-directory",
        str(runtime_root),
        "-p",
        project,
    ]
    for env_file in env_files:
        command.extend(["--env-file", str(env_file)])
    for config_file in config_files:
        command.extend(["-f", str(config_file)])
    command.extend(["-f", str((runtime_root / OVERLAY).resolve())])
    return command


def _recreate_public_stack(
    runtime_root: Path,
    project: str,
    config_files: list[Path],
    env_files: list[Path],
    expected_sha: str,
) -> None:
    overlay = runtime_root / OVERLAY
    nginx = runtime_root / STATIC_NGINX
    if not overlay.is_file():
        raise ReconcileError("public_dev_overlay_missing")
    if not nginx.is_file():
        raise ReconcileError("public_dev_nginx_missing")

    env = os.environ.copy()
    env["REQSYS_BUILD_SHA"] = expected_sha
    base = _compose_base(runtime_root, project, config_files, env_files)

    _run(base + ["config", "--quiet"], cwd=runtime_root, env=env, timeout=90)
    _run(
        base
        + [
            "up",
            "-d",
            "--build",
            "--no-deps",
            "api",
            "frontend",
            "nginx",
        ],
        cwd=runtime_root,
        env=env,
        timeout=900,
    )


def _probe(url: str, *, timeout: float = 15.0, max_bytes: int = 524_288) -> dict[str, Any]:
    started = time.monotonic()
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ReqSysPublicDevReconcile/1.0", "Accept": "*/*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(max_bytes)
            return {
                "status": int(response.status),
                "content_type": response.headers.get("Content-Type") or "",
                "body": body.decode("utf-8", errors="replace"),
                "latency_ms": round((time.monotonic() - started) * 1000, 2),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": int(exc.code),
            "content_type": exc.headers.get("Content-Type") or "",
            "body": exc.read(max_bytes).decode("utf-8", errors="replace"),
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
        }
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise ReconcileError(f"probe_failed:{type(exc).__name__}") from exc


def _json_data(result: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(result["body"])
    except json.JSONDecodeError as exc:
        raise ReconcileError("probe_json_invalid") from exc
    if not isinstance(payload, dict):
        raise ReconcileError("probe_json_not_object")
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise ReconcileError("probe_json_data_invalid")
    return data


def _verify(expected_sha: str) -> dict[str, Any]:
    expected = expected_sha.lower()
    deadline = time.monotonic() + 120
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            direct_build = _probe(f"http://127.0.0.1:{DEV_API_PORT}/api/runtime/build-info")
            direct_health = _probe(f"http://127.0.0.1:{DEV_API_PORT}/api/runtime/health")
            gateway_health = _probe(f"http://127.0.0.1:{DEV_GATEWAY_PORT}/api/runtime/health")
            gateway_ready = _probe(f"http://127.0.0.1:{DEV_GATEWAY_PORT}/api/runtime/readiness")
            gateway_build = _probe(f"http://127.0.0.1:{DEV_GATEWAY_PORT}/api/runtime/build-info")
            frontend = _probe(f"http://127.0.0.1:{DEV_GATEWAY_PORT}/task-console")
            vite = _probe(f"http://127.0.0.1:{DEV_GATEWAY_PORT}/@vite/client")

            direct_sha = str(_json_data(direct_build).get("build_sha") or "").strip().lower()
            gateway_sha = str(_json_data(gateway_build).get("build_sha") or "").strip().lower()
            html = frontend["body"]
            static_ok = (
                frontend["status"] == 200
                and "/assets/" in html
                and "/src/main.js" not in html
                and vite["status"] == 404
            )
            required_ok = all(
                item["status"] == 200
                for item in (
                    direct_build,
                    direct_health,
                    gateway_health,
                    gateway_ready,
                    gateway_build,
                )
            )
            if required_ok and direct_sha == expected and gateway_sha == expected and static_ok:
                return {
                    "build_sha": gateway_sha,
                    "direct_api_sha": direct_sha,
                    "runtime_health": "ok",
                    "readiness": "ready",
                    "frontend_static": True,
                    "vite_client_http": vite["status"],
                    "frontend_latency_ms_local": frontend["latency_ms"],
                    "gateway_health_latency_ms_local": gateway_health["latency_ms"],
                }
            last = {
                "direct_sha": direct_sha,
                "gateway_sha": gateway_sha,
                "frontend_http": frontend["status"],
                "vite_http": vite["status"],
                "static_ok": static_ok,
            }
        except ReconcileError as exc:
            last = {"error": str(exc)}
        time.sleep(2)
    raise ReconcileError("runtime_verification_timeout:" + json.dumps(last, sort_keys=True))


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise ReconcileError(f"confirmation_required:{CONFIRMATION}")
    if args.environment != "dev":
        raise ReconcileError("environment_must_be_dev")
    _require_host()

    project, runtime_root, config_files, env_files = _discover_runtime()
    sync = _sync_repo(runtime_root, args.expected_sha)
    _recreate_public_stack(
        runtime_root,
        project,
        config_files,
        env_files,
        args.expected_sha,
    )
    runtime = _verify(args.expected_sha)

    evidence = {
        "schema_version": "1.0.0",
        "status": "ready",
        "environment": "dev",
        "host": EXPECTED_HOST,
        "project": project,
        "expected_sha": args.expected_sha.lower(),
        "correlation_id": args.correlation_id,
        "sync": sync,
        "runtime": runtime,
        "frontend_mode": "static_nginx",
        "vite_hmr_exposed": False,
        "production_touched": False,
        "secrets_read": False,
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
            "expected_sha": args.expected_sha,
            "correlation_id": args.correlation_id,
            "reason": type(exc).__name__,
            "detail": str(exc)[:360],
            "production_touched": False,
            "secrets_read": False,
        }
        args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.write_text(
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
