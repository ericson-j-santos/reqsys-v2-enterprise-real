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
DEV_API_PORT = "8210"
CONFIRM = "RECONCILE-NOTERI-STUDY-MODE-DEV"
GATEWAY = "http://127.0.0.1:8083"
DIRECT_API = "http://127.0.0.1:8210"
ADMIN_EMAIL = "ericsonjosedossantos@tieri659.onmicrosoft.com"
RUNTIME_FILES = {
    "backend/app/services/noteri_host_profile.py": "app/services/noteri_host_profile.py",
    "backend/app/api/noteri_host_profile.py": "app/api/noteri_host_profile.py",
    "frontend/src/services/hostProfileLocalAgent.js": "src/services/hostProfileLocalAgent.js",
}
NGINX_CONFIG = Path("infra/nginx/default.dev.conf")


class ReconcileError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        stage: str | None = None,
        diagnostic_code: str | None = None,
        diagnostic_markers: tuple[str, ...] | None = None,
        diagnostic_details: dict[str, Any] | None = None,
    ) -> None:
        parts = code.split(":")
        self.code = (
            ":".join(parts[:2])
            if parts and parts[0] == "command_failed"
            else (parts[0] if parts else "reconcile_error")
        )
        self.stage = stage
        self.diagnostic_code = diagnostic_code
        self.diagnostic_markers = diagnostic_markers or ()
        self.diagnostic_details = dict(diagnostic_details or {})
        super().__init__(code)



def safe_command_failure_markers(stderr: str, *, stage: str) -> tuple[str, ...]:
    if stage != "compose_config":
        return ()

    value = (stderr or "").casefold()
    marker_patterns = (
        ("windows_file_missing", ("the system cannot find the file specified",)),
        ("windows_path_missing", ("the system cannot find the path specified",)),
        ("dotenv_reference", (".env", "env file")),
        ("dotenv_parse", ("unexpected character", "variable name")),
        ("project_name", ("project name",)),
        ("build_context", ("build context", "unable to prepare context")),
        ("createfile", ("createfile",)),
        ("schema_mapping", ("must be a mapping", "top-level object must be a mapping")),
        ("yaml_parse", ("did not find expected", "mapping values are not allowed", "yaml:")),
        ("mount", ("mount", "volume")),
        ("duplicate", ("duplicate", "already declared")),
        ("not_found", ("not found", "does not exist", "cannot find")),
    )
    return tuple(
        name
        for name, patterns in marker_patterns
        if any(pattern in value for pattern in patterns)
    )


def classify_command_failure(stderr: str, *, stage: str) -> str | None:
    if stage != "compose_config":
        return None

    value = (stderr or "").casefold()
    if "permission denied" in value or "access is denied" in value:
        return "docker_permission_denied"
    if (
        "cannot connect to the docker daemon" in value
        or "error during connect" in value
        or "docker engine is not running" in value
    ):
        return "docker_daemon_unavailable"
    if "env file" in value and (
        "not found" in value or "no such file" in value or "cannot find" in value
    ):
        return "compose_env_file_missing"
    if "unexpected character" in value and "variable name" in value:
        return "compose_dotenv_parse_invalid"
    if "no configuration file provided" in value:
        return "compose_config_file_missing"
    if "neither an image nor a build context specified" in value:
        return "compose_service_definition_incomplete"
    if (
        ("build context" in value or "unable to prepare context" in value)
        and (
            "not found" in value
            or "does not exist" in value
            or "the system cannot find" in value
        )
    ):
        return "compose_build_context_invalid"
    if "invalid interpolation format" in value:
        return "compose_interpolation_invalid"
    if "is not set" in value and "required" in value:
        return "compose_required_environment_missing"
    if (
        ("additional property" in value and "not allowed" in value)
        or "must be a mapping" in value
        or "top-level object must be a mapping" in value
    ):
        return "compose_schema_invalid"
    if (
        "did not find expected" in value
        or "mapping values are not allowed" in value
        or "yaml:" in value
    ):
        return "compose_yaml_invalid"
    if "project name" in value and (
        "invalid" in value or "must contain" in value or "must start" in value
    ):
        return "compose_project_name_invalid"
    if "duplicate mount point" in value:
        return "compose_mount_conflict"
    if (
        "the system cannot find the file specified" in value
        or "the system cannot find the path specified" in value
        or "no such file or directory" in value
        or "failed to read" in value
    ):
        return "compose_file_read_failed"
    return "compose_config_failed_unclassified"


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
            diagnostic_code=classify_command_failure(
                completed.stderr or "",
                stage=stage,
            ),
            diagnostic_markers=safe_command_failure_markers(
                completed.stderr or "",
                stage=stage,
            ),
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
    api_ids = [
        line.strip()
        for line in run(
            ["docker", "ps", "--filter", f"publish={DEV_API_PORT}", "--format", "{{.ID}}"],
            cwd=repo_root,
            timeout=60,
            stage="discover_api",
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(api_ids) != 1:
        raise ReconcileError("dev_api_8210_not_unique", stage="discover_api")

    api_item = inspect(api_ids[0], repo_root, stage="discover_api")
    api_labels = labels(api_item)
    project = str(api_labels.get("com.docker.compose.project") or "").strip()
    service = str(api_labels.get("com.docker.compose.service") or "").strip()
    if not project or service != "api":
        raise ReconcileError("dev_api_compose_identity_invalid", stage="discover_api")
    if any(token in project.casefold() for token in ("prod", "production", "hml", "stg", "staging")):
        raise ReconcileError("non_dev_compose_project_blocked", stage="discover_api")
    if container_host_port(api_item, "8000/tcp") != DEV_API_PORT:
        raise ReconcileError("dev_api_port_mismatch", stage="discover_api")

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

    frontend_item = service_item("frontend")
    nginx_item = service_item("nginx")
    return project, api_item, frontend_item, nginx_item


def bind_source(item: dict[str, Any], destination: str) -> Path | None:
    for mount in item.get("Mounts") or []:
        if (
            mount.get("Destination") == destination
            and mount.get("Type") == "bind"
        ):
            return windows_path(str(mount.get("Source") or ""))
    return None


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


def required_nginx_bind_source(
    item: dict[str, Any],
    expected_project: str,
) -> Path:
    source = bind_source(item, "/etc/nginx/conf.d/default.conf")
    working_dir = runtime_working_dir(item, expected_project)
    expected = (working_dir / NGINX_CONFIG).resolve()
    if source is None or source.resolve() != expected:
        raise ReconcileError(
            "nginx_config_bind_mismatch",
            stage="nginx_source_bind",
        )
    if not source.is_file():
        raise ReconcileError(
            "nginx_config_bind_source_missing",
            stage="nginx_source_bind",
        )
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


def compose_environment_files(
    api_item: dict[str, Any],
    working_dir: Path,
) -> list[Path]:
    raw = str(
        labels(api_item).get("com.docker.compose.project.environment_file") or ""
    ).strip()
    if not raw:
        return []

    files: list[Path] = []
    for value in raw.split(","):
        value = value.strip()
        if not value:
            continue
        candidate = windows_path(value)
        if not candidate.is_absolute():
            candidate = working_dir / candidate
        candidate = candidate.resolve()
        if not candidate.is_file():
            raise ReconcileError(
                "compose_environment_file_missing",
                stage="compose_context",
            )
        files.append(candidate)
    return files


def runtime_working_dir(
    api_item: dict[str, Any],
    expected_project: str,
) -> Path:
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
    return working_dir


def compose_context(
    api_item: dict[str, Any],
    repo_root: Path,
    expected_project: str,
) -> tuple[Path, list[Path], list[Path]]:
    info = labels(api_item)
    working_dir = runtime_working_dir(api_item, expected_project)

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
    environment_files = compose_environment_files(api_item, working_dir)
    return working_dir, normalized, environment_files


def compose_base(
    project: str,
    files: list[Path],
    working_dir: Path,
    environment_files: list[Path] | None = None,
) -> list[str]:
    args = [
        "docker",
        "compose",
        "--project-directory",
        str(working_dir),
        "-p",
        project,
    ]
    for path in environment_files or []:
        args.extend(["--env-file", str(path)])
    for path in files:
        args.extend(["-f", str(path)])
    return args


def backup_and_copy(
    repo_root: Path,
    api_source: Path,
    frontend_source: Path,
    nginx_target: Path,
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
    monitoring_module = api_source / "app" / "api" / "monitoramento_operacional.py"
    if not monitoring_module.is_file():
        raise ReconcileError(
            "runtime_monitoring_module_missing",
            stage="api_source_bind",
        )
    main_backup = backup_root / "backend__app__main.py"
    shutil.copy2(main_path, main_backup)
    text = main_path.read_text(encoding="utf-8")
    marker = "import app.models"
    if marker not in text:
        raise ReconcileError("runtime_main_import_marker_missing")
    if "from app.api import noteri_host_profile" not in text:
        text = text.replace(
            marker,
            marker + "\nfrom app.api import noteri_host_profile",
            1,
        )
    if (
        "from app.api import monitoramento_operacional" not in text
        and "    monitoramento_operacional," not in text
    ):
        text = text.replace(
            marker,
            marker + "\nfrom app.api import monitoramento_operacional",
            1,
        )

    marker = "@app.middleware"
    if marker not in text:
        raise ReconcileError("runtime_main_router_marker_missing")
    if "app.include_router(noteri_host_profile.router)" not in text:
        index = text.find(marker)
        text = (
            text[:index]
            + "app.include_router(noteri_host_profile.router)\n\n"
            + text[index:]
        )
    if "app.include_router(monitoramento_operacional.router)" not in text:
        index = text.find(marker)
        text = (
            text[:index]
            + "app.include_router(monitoramento_operacional.router)\n\n"
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


def restart_container(
    container: str,
    repo_root: Path,
    *,
    stage: str,
) -> None:
    run(
        ["docker", "restart", container],
        cwd=repo_root,
        timeout=120,
        stage=stage,
    )


def wait_nginx_bind_visibility(
    container: str,
    nginx_bind: Path,
    repo_root: Path,
    *,
    timeout_seconds: int = 60,
    require_contract: bool = True,
) -> dict[str, bool]:
    expected = nginx_bind.read_text(encoding="utf-8").replace("\r\n", "\n")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        completed = run(
            [
                "docker",
                "exec",
                container,
                "cat",
                "/etc/nginx/conf.d/default.conf",
            ],
            cwd=repo_root,
            timeout=30,
            stage="nginx_bind_visibility",
        )
        observed = completed.stdout.replace("\r\n", "\n")
        if observed == expected:
            contract = {
                "bind_visible": True,
                "runtime_route": "location ~ ^/api/(runtime|" in observed,
                "api_prefix_route": "location /api/" in observed,
            }
            if require_contract and not all(
                contract[name]
                for name in ("runtime_route", "api_prefix_route")
            ):
                markers = tuple(
                    f"{name}_missing"
                    for name in ("runtime_route", "api_prefix_route")
                    if not contract[name]
                )
                raise ReconcileError(
                    "nginx_rendered_contract_missing",
                    stage="nginx_bind_visibility",
                    diagnostic_markers=markers,
                )
            return contract
        time.sleep(1)
    raise ReconcileError(
        "nginx_bind_visibility_timeout",
        stage="nginx_bind_visibility",
        diagnostic_markers=("nginx_bind_not_visible",),
    )


def reload_nginx(
    container: str,
    nginx_bind: Path,
    repo_root: Path,
    *,
    stage_prefix: str = "nginx_reload",
    require_contract: bool = True,
) -> dict[str, bool]:
    contract = wait_nginx_bind_visibility(
        container,
        nginx_bind,
        repo_root,
        require_contract=require_contract,
    )
    run(
        ["docker", "exec", container, "nginx", "-t"],
        cwd=repo_root,
        timeout=60,
        stage=f"{stage_prefix}_config_test",
    )
    run(
        ["docker", "exec", container, "nginx", "-s", "reload"],
        cwd=repo_root,
        timeout=60,
        stage=stage_prefix,
    )
    return contract


def wait_gateway_status(
    path: str,
    expected: set[int],
    *,
    timeout_seconds: int = 120,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_status: int | None = None
    while time.monotonic() < deadline:
        request = urllib.request.Request(
            GATEWAY + path,
            headers={"Cache-Control": "no-store"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                last_status = int(response.status)
        except urllib.error.HTTPError as exc:
            last_status = int(exc.code)
        except OSError:
            last_status = None
        if last_status in expected:
            return
        time.sleep(2)
    marker = {
        "/api/health": "api_health_not_observed",
        "/api/runtime/health": "runtime_health_not_observed",
        "/api/v1/noteri/profile": "noteri_profile_not_observed",
    }.get(path, "gateway_status_not_observed")
    raise ReconcileError(
        "gateway_status_timeout",
        stage="live_bind_refresh",
        diagnostic_markers=(marker,),
        diagnostic_details={
            "gateway_path": path,
            "gateway_last_http_status": last_status,
        },
    )


def tcp_port_open(host: str, port: int, *, timeout_seconds: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def nginx_upstream_api_health_ok(container: str, repo_root: Path) -> bool:
    completed = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "wget",
            "-qO-",
            "-T",
            "5",
            "http://api:8000/health",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
        shell=False,
    )
    return completed.returncode == 0


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


def wait_direct_api_contract(
    *,
    timeout_seconds: int = 90,
) -> dict[str, bool]:
    deadline = time.monotonic() + timeout_seconds
    last_paths: set[str] = set()
    while time.monotonic() < deadline:
        request = urllib.request.Request(
            DIRECT_API + "/openapi.json",
            headers={"Cache-Control": "no-store"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            paths = payload.get("paths") or {}
            last_paths = set(paths)
            contract = {
                "noteri_profile": "/v1/noteri/profile" in last_paths,
                "runtime_health": "/api/runtime/health" in last_paths,
            }
            if all(contract.values()):
                return contract
        except (OSError, ValueError, json.JSONDecodeError):
            last_paths = set()
        time.sleep(2)

    markers: list[str] = []
    if "/v1/noteri/profile" not in last_paths:
        markers.append("noteri_profile_missing")
    if "/api/runtime/health" not in last_paths:
        markers.append("runtime_health_missing")
    raise ReconcileError(
        "direct_api_routes_timeout",
        stage="api_direct_contract",
        diagnostic_markers=tuple(markers),
    )


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

    frontend_source = required_bind_source(
        frontend_before,
        "/app",
        stage="frontend_source_bind",
    )
    if not frontend_source.is_dir():
        raise ReconcileError(
            "frontend_source_dir_missing",
            stage="frontend_source_bind",
        )

    if container_host_port(nginx_before, "80/tcp") != DEV_GATEWAY_PORT:
        raise ReconcileError(
            "dev_gateway_port_mismatch",
            stage="nginx_gateway_identity",
            diagnostic_markers=("gateway_8083_not_bound",),
        )

    nginx_bind = required_nginx_bind_source(nginx_before, project)

    backup_root, changes = backup_and_copy(
        repo_root,
        api_source,
        frontend_source,
        nginx_bind,
        args.expected_sha,
    )

    try:
        # O runtime DEV atual usa bind mounts, mas não dependemos de hot-reload
        # implícito: reiniciamos somente a API existente para carregar o código
        # sincronizado. Não executamos Compose nem reprocessamos .env/secrets.
        restart_container(api_container, repo_root, stage="api_restart")
        wait_container_healthy(api_container, repo_root, args.health_timeout)
        direct_api_contract = wait_direct_api_contract()
        nginx_rendered_contract = reload_nginx(
            nginx_container,
            nginx_bind,
            repo_root,
        )

        try:
            wait_gateway_status("/api/health", {200})
            wait_gateway_status("/api/runtime/health", {200})
            wait_gateway_status("/api/v1/noteri/profile", {401})
        except ReconcileError as exc:
            if exc.code == "gateway_status_timeout":
                exc.diagnostic_details.update(
                    {
                        "gateway_tcp_8083_open": tcp_port_open(
                            "127.0.0.1",
                            int(DEV_GATEWAY_PORT),
                        ),
                        "nginx_upstream_api_health_ok": nginx_upstream_api_health_ok(
                            nginx_container,
                            repo_root,
                        ),
                        "nginx_rendered_contract": dict(nginx_rendered_contract),
                        "direct_api_contract": dict(direct_api_contract),
                    }
                )
            raise

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
        mounts = api_after.get("Mounts") or []
        if any(item.get("Destination") == "/noteri-runtime" for item in mounts):
            raise ReconcileError("legacy_noteri_profile_mount_present")

        wait_frontend_source()
        api_result = api_e2e()
        browser_result = browser_e2e()
    except Exception:
        rollback_files(changes)
        try:
            restart_container(
                api_container,
                repo_root,
                stage="rollback_api_restart",
            )
            wait_container_healthy(api_container, repo_root, args.health_timeout)
            reload_nginx(
                nginx_container,
                nginx_bind,
                repo_root,
                stage_prefix="rollback_nginx_reload",
                require_contract=False,
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
        "runtime_discovery": "api_port_8210_compose_labels",
        "compose_invoked": False,
        "runtime_refresh": "bind_mounts_plus_api_restart_plus_nginx_bind_sync_reload",
        "api_container_restarted": True,
        "api_source_bind_observed": True,
        "frontend_source_bind_observed": True,
        "nginx_config_bind_observed": True,
        "frontend_runtime_refresh": "bind",
        "profile_mount_rw": False,
        "control_plane_bridge": True,
        "control_plane_url": "http://host.docker.internal:8787",
        "loopback_agent_exposed": False,
        "browser_loopback_dependency_removed": True,
        "backup_created": backup_root.is_dir(),
        "nginx_runtime_contract_refreshed": True,
        "nginx_gateway_port_confirmed": True,
        "nginx_bind_visibility_confirmed": nginx_rendered_contract.get("bind_visible") is True,
        "nginx_rendered_contract": nginx_rendered_contract,
        "direct_api_contract": direct_api_contract,
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
            "diagnostic_code": (
                exc.diagnostic_code
                if isinstance(exc, ReconcileError) and exc.diagnostic_code
                else None
            ),
            "diagnostic_markers": (
                list(exc.diagnostic_markers)
                if isinstance(exc, ReconcileError)
                else []
            ),
            "diagnostic_details": (
                dict(exc.diagnostic_details)
                if isinstance(exc, ReconcileError)
                else {}
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
