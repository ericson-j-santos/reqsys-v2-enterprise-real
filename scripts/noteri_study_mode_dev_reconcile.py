#!/usr/bin/env python3
"""Reconcilia e valida o Modo ESTUDO no runtime DEV público do PC24x7.

O script é propositalmente restrito:
- runtime fixo DESKTOP-PDQK954;
- ambiente DEV descoberto pelo gateway local exclusivo na porta 8083;
- projeto/containers derivados dos labels Docker Compose do gateway observado;
- transporte de perfil pelo Engineering Orchestrator;
- destino lógico fixo Noteri;
- sem HML/PROD;
- sem leitura de segredos;
- sem shell;
- restaura NORMAL ao fim do E2E.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
DEV_GATEWAY_PORT = "8083"
CONFIRM = "RECONCILE-NOTERI-STUDY-MODE-DEV"
GATEWAY = "http://127.0.0.1:8083"
ADMIN_EMAIL = "ericsonjosedossantos@tieri659.onmicrosoft.com"
RUNTIME_FILES = {
    "backend/app/services/noteri_host_profile.py": "app/services/noteri_host_profile.py",
    "backend/app/api/noteri_host_profile.py": "app/api/noteri_host_profile.py",
    "frontend/src/services/hostProfileLocalAgent.js": "src/services/hostProfileLocalAgent.js",
}
NGINX_CONFIG = Path("infra/nginx/default.dev.conf")


class ReconcileError(RuntimeError):
    def __init__(self, code: str, *, stage: str | None = None) -> None:
        parts = code.split(":")
        self.code = (
            ":".join(parts[:2])
            if parts and parts[0] == "command_failed"
            else (parts[0] if parts else "reconcile_error")
        )
        self.stage = stage
        super().__init__(code)


def run(
    args: list[str],
    *,
    cwd: Path,
    timeout: int = 300,
    env: dict[str, str] | None = None,
    stage: str = "runtime_command",
) -> subprocess.CompletedProcess[str]:
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
        env=env,
    )
    if completed.returncode != 0:
        raise ReconcileError(
            f"command_failed:{Path(args[0]).name}:exit_{completed.returncode}",
            stage=stage,
        )
    return completed


def git_head(repo_root: Path) -> str:
    return run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        timeout=30,
        stage="preconditions",
    ).stdout.strip()


def require_host() -> None:
    if os.name != "nt":
        raise ReconcileError("windows_required")
    if socket.gethostname().casefold() != EXPECTED_HOST.casefold():
        raise ReconcileError("host_not_allowed")


def inspect(
    container: str,
    repo_root: Path,
    *,
    stage: str = "inspect_runtime",
) -> dict[str, Any]:
    raw = run(
        ["docker", "inspect", container],
        cwd=repo_root,
        timeout=60,
        stage=stage,
    ).stdout
    payload = json.loads(raw)
    if not isinstance(payload, list) or len(payload) != 1:
        raise ReconcileError(f"docker_inspect_invalid:{container}")
    return payload[0]


def labels(item: dict[str, Any]) -> dict[str, str]:
    return (item.get("Config") or {}).get("Labels") or {}


def container_name(item: dict[str, Any]) -> str:
    return str(item.get("Name") or "").lstrip("/")


def discover_runtime(repo_root: Path) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    gateway_ids = [
        line.strip()
        for line in run(
            ["docker", "ps", "--filter", f"publish={DEV_GATEWAY_PORT}", "--format", "{{.ID}}"],
            cwd=repo_root,
            timeout=60,
            stage="discover_gateway",
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(gateway_ids) != 1:
        raise ReconcileError("dev_gateway_8083_not_unique", stage="discover_gateway")

    nginx_item = inspect(gateway_ids[0], repo_root, stage="discover_gateway")
    nginx_labels = labels(nginx_item)
    project = str(nginx_labels.get("com.docker.compose.project") or "").strip()
    service = str(nginx_labels.get("com.docker.compose.service") or "").strip()
    if not project or service != "nginx":
        raise ReconcileError("dev_gateway_compose_identity_invalid", stage="discover_gateway")
    if any(token in project.casefold() for token in ("prod", "production", "hml", "stg", "staging")):
        raise ReconcileError("non_dev_compose_project_blocked", stage="discover_gateway")
    if container_host_port(nginx_item, "80/tcp") != DEV_GATEWAY_PORT:
        raise ReconcileError("dev_gateway_port_mismatch", stage="discover_gateway")

    def service_item(expected_service: str) -> dict[str, Any]:
        ids = [
            line.strip()
            for line in run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    f"label=com.docker.compose.project={project}",
                    "--filter",
                    f"label=com.docker.compose.service={expected_service}",
                    "--format",
                    "{{.ID}}",
                ],
                cwd=repo_root,
                timeout=60,
                stage="discover_runtime",
            ).stdout.splitlines()
            if line.strip()
        ]
        if len(ids) != 1:
            raise ReconcileError(
                f"runtime_service_not_unique:{expected_service}",
                stage="discover_runtime",
            )
        return inspect(ids[0], repo_root, stage="discover_runtime")

    api_item = service_item("api")
    frontend_item = service_item("frontend")
    return project, api_item, frontend_item, nginx_item


def rw_bind_source(item: dict[str, Any], destination: str) -> Path | None:
    for mount in item.get("Mounts") or []:
        if (
            mount.get("Destination") == destination
            and mount.get("Type") == "bind"
            and mount.get("RW") is True
        ):
            return windows_path(str(mount.get("Source") or ""))
    return None


def required_bind_source(
    item: dict[str, Any],
    destination: str,
    *,
    stage: str,
) -> Path:
    source = rw_bind_source(item, destination)
    if source is None:
        raise ReconcileError(f"rw_bind_missing:{destination}", stage=stage)
    return source


def windows_path(raw: str) -> Path:
    value = raw.strip()
    lowered = value.lower()
    for prefix in ("/run/desktop/mnt/host/", "/host_mnt/"):
        if lowered.startswith(prefix):
            tail = value[len(prefix):]
            parts = tail.split("/", 1)
            if len(parts) == 2 and len(parts[0]) == 1:
                return Path(f"{parts[0].upper()}:/{parts[1]}")
    return Path(value)


def container_host_port(item: dict[str, Any], port: str) -> str | None:
    bindings = ((item.get("NetworkSettings") or {}).get("Ports") or {}).get(port)
    if not bindings:
        return None
    value = str((bindings[0] or {}).get("HostPort") or "").strip()
    return value or None


def compose_context(
    api_item: dict[str, Any],
    repo_root: Path,
    expected_project: str,
) -> tuple[Path, list[Path]]:
    info = labels(api_item)
    project = info.get("com.docker.compose.project")
    if project != expected_project:
        raise ReconcileError(f"compose_project_mismatch:{project}")

    working_raw = info.get("com.docker.compose.project.working_dir") or ""
    if not working_raw:
        raise ReconcileError("compose_working_dir_missing")
    working_dir = windows_path(working_raw)
    if not working_dir.is_dir():
        raise ReconcileError("compose_working_dir_not_found")

    files_raw = info.get("com.docker.compose.project.config_files") or ""
    files: list[Path] = []
    for raw in files_raw.split(","):
        if raw.strip():
            candidate = windows_path(raw.strip())
            if candidate.is_file():
                files.append(candidate)

    if not files:
        for name in ("docker-compose.yml", "docker-compose.dev.yml"):
            candidate = working_dir / name
            if candidate.is_file():
                files.append(candidate)

    if not files:
        raise ReconcileError("compose_config_files_not_found")

    stable_root = Path(os.environ.get("LOCALAPPDATA", "")) / "ReqSys" / "StudyModeDeploy"
    stable_root.mkdir(parents=True, exist_ok=True)
    stable_override = stable_root / "docker-compose.noteri-study-mode.yml"
    template = repo_root / "docker-compose.noteri-study-mode.yml"
    stable_override.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")

    normalized = [path.resolve() for path in files if path.resolve() != stable_override.resolve()]
    normalized.append(stable_override.resolve())
    return working_dir, normalized


def compose_base(project: str, files: list[Path], working_dir: Path) -> list[str]:
    args = [
        "docker",
        "compose",
        "--project-directory",
        str(working_dir),
        "-p",
        project,
    ]
    for path in files:
        args.extend(["-f", str(path)])
    return args


def backup_and_copy(
    repo_root: Path,
    api_source: Path,
    frontend_source: Path,
    working_dir: Path,
    expected_sha: str,
) -> tuple[Path, list[tuple[Path, Path | None]]]:
    stable_root = Path(os.environ.get("LOCALAPPDATA", "")) / "ReqSys" / "StudyModeDeploy"
    backup_root = stable_root / "backups" / expected_sha
    backup_root.mkdir(parents=True, exist_ok=True)
    changes: list[tuple[Path, Path | None]] = []

    for source_rel, target_rel in RUNTIME_FILES.items():
        source = repo_root / source_rel
        base = api_source if source_rel.startswith("backend/") else frontend_source
        target = base / target_rel
        if not source.is_file():
            raise ReconcileError(f"source_file_missing:{source_rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = None
        if target.exists():
            backup = backup_root / source_rel.replace("/", "__")
            shutil.copy2(target, backup)
        shutil.copy2(source, target)
        changes.append((target, backup))

    nginx_source = repo_root / NGINX_CONFIG
    nginx_target = working_dir / NGINX_CONFIG
    if not nginx_source.is_file():
        raise ReconcileError("nginx_config_source_missing")
    nginx_target.parent.mkdir(parents=True, exist_ok=True)
    nginx_backup = None
    if nginx_target.exists():
        nginx_backup = backup_root / "infra__nginx__default.dev.conf"
        shutil.copy2(nginx_target, nginx_backup)
    shutil.copy2(nginx_source, nginx_target)
    changes.append((nginx_target, nginx_backup))

    main_path = api_source / "app" / "main.py"
    if not main_path.is_file():
        raise ReconcileError("runtime_main_missing")
    main_backup = backup_root / "backend__app__main.py"
    shutil.copy2(main_path, main_backup)
    text = main_path.read_text(encoding="utf-8")
    if "from app.api import noteri_host_profile" not in text:
        marker = "import app.models"
        if marker not in text:
            raise ReconcileError("runtime_main_import_marker_missing")
        text = text.replace(
            marker,
            marker + "\nfrom app.api import noteri_host_profile",
            1,
        )
    if "app.include_router(noteri_host_profile.router)" not in text:
        marker = "@app.middleware"
        index = text.find(marker)
        if index < 0:
            raise ReconcileError("runtime_main_router_marker_missing")
        text = (
            text[:index]
            + "app.include_router(noteri_host_profile.router)\n\n"
            + text[index:]
        )
    main_path.write_text(text, encoding="utf-8")
    changes.append((main_path, main_backup))
    return backup_root, changes


def rollback_files(changes: list[tuple[Path, Path | None]]) -> None:
    for target, backup in reversed(changes):
        try:
            if backup and backup.is_file():
                shutil.copy2(backup, target)
            elif target.exists():
                target.unlink()
        except OSError:
            pass


def wait_container_healthy(
    container: str,
    repo_root: Path,
    timeout_seconds: int = 180,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last = "unknown"
    while time.monotonic() < deadline:
        item = inspect(container, repo_root, stage="api_health")
        state = item.get("State") or {}
        health = state.get("Health") or {}
        last = str(health.get("Status") or state.get("Status") or "unknown").lower()
        if last in {"healthy", "running"}:
            return
        time.sleep(2)
    raise ReconcileError(f"api_health_timeout:{last}")


def http_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    correlation_id: str | None = None,
    body: dict[str, Any] | None = None,
    expected: set[int] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Cache-Control": "no-store"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    request = urllib.request.Request(
        GATEWAY + path,
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = int(response.status)
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        payload = json.loads(exc.read().decode("utf-8") or "{}")
    allowed = expected or {200}
    if status not in allowed:
        raise ReconcileError(f"http_unexpected:{method}:{path}:{status}")
    return status, payload


def login_admin() -> tuple[str, dict[str, Any]]:
    _, payload = http_json(
        "POST",
        "/api/v1/auth/login",
        body={"email": ADMIN_EMAIL},
    )
    data = payload.get("data") or {}
    token = str(data.get("access_token") or "")
    usuario = data.get("usuario") or {}
    if not token or usuario.get("papel") != "admin":
        raise ReconcileError("admin_login_unavailable")
    return token, usuario


def profile_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") or {}
    if data.get("host") != "Noteri":
        raise ReconcileError("profile_host_mismatch")
    return data


def wait_frontend_source() -> None:
    deadline = time.monotonic() + 90
    url = GATEWAY + "/src/services/hostProfileLocalAgent.js"
    last = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                last = response.read().decode("utf-8", "replace")
            if "/v1/noteri/profile" in last and "127.0.0.1:8765" not in last:
                return
        except OSError:
            pass
        time.sleep(2)
    raise ReconcileError("frontend_same_origin_source_not_observed")


def api_e2e() -> dict[str, Any]:
    no_auth, _ = http_json(
        "GET",
        "/api/v1/noteri/profile",
        expected={401},
    )
    if no_auth != 401:
        raise ReconcileError("negative_auth_control_failed")

    token, usuario = login_admin()
    _, before_payload = http_json(
        "GET",
        "/api/v1/noteri/profile",
        token=token,
    )
    before = profile_data(before_payload)

    corr1 = f"study-dev-e2e-{int(time.time())}-1"
    _, changed_payload = http_json(
        "POST",
        "/api/v1/noteri/profile",
        token=token,
        correlation_id=corr1,
        body={"profile": "ESTUDO", "correlation_id": corr1},
    )
    changed = profile_data(changed_payload)
    if changed.get("profile") != "ESTUDO" or changed.get("changed") is not True:
        raise ReconcileError("estudo_change_failed")

    _, readback_payload = http_json(
        "GET",
        "/api/v1/noteri/profile",
        token=token,
    )
    readback = profile_data(readback_payload)
    if readback.get("profile") != "ESTUDO" or readback.get("accepts_new_development") is not False:
        raise ReconcileError("estudo_readback_failed")

    corr2 = f"study-dev-e2e-{int(time.time())}-2"
    _, replay_payload = http_json(
        "POST",
        "/api/v1/noteri/profile",
        token=token,
        correlation_id=corr2,
        body={"profile": "ESTUDO", "correlation_id": corr2},
    )
    replay = profile_data(replay_payload)
    if replay.get("changed") is not False:
        raise ReconcileError("estudo_idempotency_failed")

    corr3 = f"study-dev-e2e-{int(time.time())}-3"
    _, restored_payload = http_json(
        "POST",
        "/api/v1/noteri/profile",
        token=token,
        correlation_id=corr3,
        body={"profile": "NORMAL", "correlation_id": corr3},
    )
    restored = profile_data(restored_payload)
    if restored.get("profile") != "NORMAL" or restored.get("accepts_new_development") is not True:
        raise ReconcileError("normal_restore_failed")

    return {
        "negative_unauthenticated_status": 401,
        "initial_profile": before.get("profile"),
        "estudo_changed": True,
        "estudo_readback": True,
        "idempotent_replay": True,
        "final_profile": "NORMAL",
        "admin_role_confirmed": usuario.get("papel") == "admin",
    }


def browser_e2e() -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ReconcileError("playwright_not_installed") from exc

    token, usuario = login_admin()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        page.goto(GATEWAY + "/login", wait_until="domcontentloaded", timeout=30000)
        page.evaluate(
            """([token, user]) => {
              localStorage.setItem('reqsys_token', token)
              localStorage.setItem('reqsys_usuario', JSON.stringify(user))
            }""",
            [token, usuario],
        )
        page.goto(GATEWAY + "/task-console", wait_until="domcontentloaded", timeout=30000)
        card = page.locator('[data-testid="noteri-study-mode-card"]')
        card.wait_for(state="visible", timeout=30000)
        study = page.get_by_role("button", name="Quero estudar agora")
        study.wait_for(state="visible", timeout=30000)
        deadline = time.monotonic() + 30
        while study.is_disabled() and time.monotonic() < deadline:
            page.wait_for_timeout(500)
        if study.is_disabled():
            raise ReconcileError("study_button_disabled")
        study.click()
        page.wait_for_function(
            """() => {
              const card = document.querySelector('[data-testid="noteri-study-mode-card"]')
              return card && card.textContent.includes('ESTUDO')
            }""",
            timeout=30000,
        )

        back = page.get_by_role("button", name="Voltar ao desenvolvimento")
        back.click()
        page.wait_for_function(
            """() => {
              const card = document.querySelector('[data-testid="noteri-study-mode-card"]')
              return card && card.textContent.includes('NORMAL')
            }""",
            timeout=30000,
        )
        browser.close()

    return {
        "task_console_loaded": True,
        "study_button_clicked": True,
        "estudo_observed_in_ui": True,
        "normal_restored_in_ui": True,
        "final_profile": "NORMAL",
    }


def execute(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    require_host()
    if args.confirm != CONFIRM:
        raise ReconcileError("confirmation_invalid")
    if git_head(repo_root) != args.expected_sha:
        raise ReconcileError("git_head_mismatch")

    project, api_before, frontend_before, nginx_before = discover_runtime(repo_root)
    for item, service in (
        (api_before, "api"),
        (frontend_before, "frontend"),
        (nginx_before, "nginx"),
    ):
        item_labels = labels(item)
        if item_labels.get("com.docker.compose.project") != project:
            raise ReconcileError(f"runtime_project_mismatch:{service}")
        if item_labels.get("com.docker.compose.service") != service:
            raise ReconcileError(f"runtime_service_mismatch:{service}")

    api_container = container_name(api_before)
    frontend_container = container_name(frontend_before)
    nginx_container = container_name(nginx_before)
    if not all((api_container, frontend_container, nginx_container)):
        raise ReconcileError("runtime_container_name_missing", stage="discover_runtime")

    api_source = required_bind_source(
        api_before,
        "/app",
        stage="api_source_bind",
    )
    working_dir, compose_files = compose_context(api_before, repo_root, project)

    frontend_bind_source = rw_bind_source(frontend_before, "/app")
    frontend_requires_rebuild = frontend_bind_source is None
    frontend_source = frontend_bind_source or (working_dir / "frontend")
    if not frontend_source.is_dir():
        raise ReconcileError(
            "frontend_source_dir_missing",
            stage="frontend_source_fallback",
        )

    backup_root, changes = backup_and_copy(
        repo_root,
        api_source,
        frontend_source,
        working_dir,
        args.expected_sha,
    )

    compose_env = os.environ.copy()
    api_port = container_host_port(api_before, "8000/tcp")
    gateway_port = container_host_port(nginx_before, "80/tcp")
    if api_port:
        compose_env["BACKEND_PORT"] = api_port
    if gateway_port:
        compose_env["GATEWAY_PORT"] = gateway_port

    base = compose_base(project, compose_files, working_dir)
    try:
        run(
            [*base, "config"],
            cwd=working_dir,
            timeout=120,
            env=compose_env,
            stage="compose_config",
        )
        run(
            [*base, "up", "-d", "--no-deps", "--force-recreate", "api"],
            cwd=working_dir,
            timeout=600,
            env=compose_env,
            stage="api_recreate",
        )
        wait_container_healthy(api_container, repo_root, args.health_timeout)

        if frontend_requires_rebuild:
            run(
                [
                    *base,
                    "up",
                    "-d",
                    "--no-deps",
                    "--build",
                    "--force-recreate",
                    "frontend",
                ],
                cwd=working_dir,
                timeout=900,
                env=compose_env,
                stage="frontend_rebuild",
            )

        run(
            [*base, "up", "-d", "--no-deps", "--force-recreate", "nginx"],
            cwd=working_dir,
            timeout=300,
            env=compose_env,
            stage="nginx_recreate",
        )

        _, public_health = http_json("GET", "/api/health")
        _, runtime_health = http_json("GET", "/api/runtime/health")
        gateway_contract = {
            "api_health": public_health.get("status") is not None,
            "runtime_health": runtime_health.get("status") is not None,
        }

        api_after = inspect(
            api_container,
            repo_root,
            stage="verify_runtime_profile",
        )
        env_items = (api_after.get("Config") or {}).get("Env") or []
        env_map = dict(entry.split("=", 1) for entry in env_items if "=" in entry)
        mounts = api_after.get("Mounts") or []
        if (
            env_map.get("NOTERI_CONTROL_PLANE_URL")
            != "http://host.docker.internal:8787"
        ):
            raise ReconcileError("runtime_control_plane_env_missing")
        if any(item.get("Destination") == "/noteri-runtime" for item in mounts):
            raise ReconcileError("legacy_noteri_profile_mount_present")

        wait_frontend_source()
        api_result = api_e2e()
        browser_result = browser_e2e()
    except Exception:
        rollback_files(changes)
        try:
            original_files = [path for path in compose_files if "StudyModeDeploy" not in str(path)]
            original_base = compose_base(project, original_files, working_dir)
            run(
                [*original_base, "up", "-d", "--no-deps", "--force-recreate", "api"],
                cwd=working_dir,
                timeout=600,
                env=compose_env,
                stage="rollback_api_recreate",
            )
            if frontend_requires_rebuild:
                run(
                    [
                        *original_base,
                        "up",
                        "-d",
                        "--no-deps",
                        "--build",
                        "--force-recreate",
                        "frontend",
                    ],
                    cwd=working_dir,
                    timeout=900,
                    env=compose_env,
                    stage="rollback_frontend_rebuild",
                )
            run(
                [*original_base, "up", "-d", "--no-deps", "--force-recreate", "nginx"],
                cwd=working_dir,
                timeout=300,
                env=compose_env,
                stage="rollback_nginx_recreate",
            )
        except Exception:
            pass
        raise

    evidence = {
        "ok": True,
        "environment": "dev",
        "host": EXPECTED_HOST,
        "project": project,
        "expected_sha": args.expected_sha,
        "api_container": api_container,
        "frontend_container": frontend_container,
        "gateway_container": nginx_container,
        "runtime_discovery": "gateway_port_8083_compose_labels",
        "api_source_bind_observed": True,
        "frontend_source_bind_observed": not frontend_requires_rebuild,
        "frontend_runtime_refresh": (
            "rebuild_from_compose_source" if frontend_requires_rebuild else "bind"
        ),
        "profile_mount_rw": False,
        "control_plane_bridge": True,
        "control_plane_url": "http://host.docker.internal:8787",
        "loopback_agent_exposed": False,
        "browser_loopback_dependency_removed": True,
        "backup_created": backup_root.is_dir(),
        "nginx_runtime_contract_refreshed": True,
        "gateway_contract": gateway_contract,
        "api_e2e": api_result,
        "browser_e2e": browser_result,
        "production_touched": False,
        "secrets_read": False,
    }
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcilia Modo ESTUDO DEV no PC24x7")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--health-timeout", type=int, default=180)
    parser.add_argument("--evidence-path", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = execute(args)
        if args.evidence_path:
            args.evidence_path.parent.mkdir(parents=True, exist_ok=True)
            args.evidence_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        failure = {
            "ok": False,
            "error": "noteri_study_mode_reconcile_failed",
            "error_type": type(exc).__name__,
            "error_code": (
                exc.code if isinstance(exc, ReconcileError) else "unexpected_error"
            ),
            "failure_stage": (
                exc.stage if isinstance(exc, ReconcileError) and exc.stage else "unknown"
            ),
            "correlation_id": f"study-mode-reconcile-{args.expected_sha[:12]}",
            "expected_sha": args.expected_sha,
            "environment": "dev",
            "host": socket.gethostname(),
            "production_touched": False,
            "secrets_read": False,
        }
        if args.evidence_path:
            args.evidence_path.parent.mkdir(parents=True, exist_ok=True)
            args.evidence_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
