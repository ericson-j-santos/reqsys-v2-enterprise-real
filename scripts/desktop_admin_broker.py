#!/usr/bin/env python3
"""Broker administrativo governado do Desktop PC24x7.

Canal outbound-only:
- consulta somente a issue operacional #1705 no GitHub via HTTPS;
- aceita somente comentários exatos do owner;
- não abre porta de rede local;
- não aceita shell, caminho, executável, host ou argumento arbitrário;
- executa somente handlers versionados e idempotentes.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
EXPECTED_ACTOR = "ericson-j-santos"
EXPECTED_ASSOCIATION = "OWNER"
REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
ISSUE_NUMBER = 1705
TASK_FOLDER = r"\Automation"
TASK_LEAF = "ReqSysDesktopAdminBroker"
TASK_NAME = TASK_FOLDER + "\\" + TASK_LEAF
TASK_TRIGGER_BOOT = 8
TASK_ACTION_EXEC = 0
TASK_LOGON_S4U = 2
TASK_CREATE_OR_UPDATE = 6
TASK_RUNLEVEL_HIGHEST = 1
TASK_INSTANCES_IGNORE_NEW = 2
INSTALL_CONFIRM = "INSTALL-DESKTOP-ADMIN-BROKER"
DEFAULT_POLL_SECONDS = 90
MAX_COMMENT_AGE_SECONDS = 300
WATCHDOG_SCRIPT = "desktop_control_plane_watchdog.py"
WATCHDOG_UAC_SCRIPT = "desktop_control_plane_watchdog_uac_launcher.py"
RDC_RECOVERY_SCRIPT = "pc24x7_rdc_recovery.py"
RUNNER_BOOTSTRAP_SCRIPT = "activate_desktop_free_control_plane.py"
RUNNER_INSTALL_SCRIPT = "install_reqsys_dev_runner.ps1"
RUNNER_ONBOARD_SCRIPT = "onboard_reqsys_dev_runner.ps1"
RUNNER_PREFLIGHT_SCRIPT = "validate_reqsys_dev_runner.py"
RUNNER_POOL_POLICY = "reqsys-dev-runner-pool.json"
RUNNER_ONBOARD_COMMAND = "/reqsys run pc24x7-runner-pool-onboard"
RUNNER_ONBOARD_ACTION = "onboard-runner-runtime"
RUNNER_ONBOARD_STAGE_CONFIRM = "STAGE-REQSYS-DEV-RUNNER-ADMIN-ONBOARD"
RUNNER_SERVICE = re.compile(r"actions\.runner\.[A-Za-z0-9_.-]+\Z")

ALLOWED_COMMANDS = {
    "/reqsys admin desktop status": "status",
    "/reqsys admin desktop recover-control-plane": "recover-control-plane",
    "/reqsys admin desktop recover-rdc": "recover-rdc",
    "/reqsys admin desktop recover-runner": "recover-runner",
    "/reqsys admin desktop activate-watchdog": "activate-watchdog",
    RUNNER_ONBOARD_COMMAND: RUNNER_ONBOARD_ACTION,
}


class BrokerError(RuntimeError):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def require_windows_desktop() -> str:
    if os.name != "nt":
        raise BrokerError("Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise BrokerError(f"host não autorizado: {host}")
    return host


def validate_sha(value: str) -> str:
    value = value.strip().lower()
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise BrokerError("source_sha inválido")
    return value


def default_runtime_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise BrokerError("LOCALAPPDATA não definido")
    return Path(base) / "ReqSys" / "DesktopAdminBroker"


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=True, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def parse_github_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise BrokerError("timestamp GitHub sem timezone")
    return parsed.astimezone(timezone.utc)


def authorize_comment(
    comment: dict[str, Any],
    *,
    not_before: datetime,
    reference_time: datetime | None = None,
) -> str | None:
    reference = reference_time or now_utc()
    user = comment.get("user") or {}
    if str(user.get("login") or "").casefold() != EXPECTED_ACTOR.casefold():
        return None
    if str(comment.get("author_association") or "").upper() != EXPECTED_ASSOCIATION:
        return None
    body = str(comment.get("body") or "").strip()
    action = ALLOWED_COMMANDS.get(body)
    if action is None:
        return None
    created = parse_github_time(str(comment.get("created_at") or ""))
    updated = parse_github_time(str(comment.get("updated_at") or ""))
    if updated != created:
        return None
    if created < not_before:
        return None
    age = (reference - created).total_seconds()
    if age < -60 or age > MAX_COMMENT_AGE_SECONDS:
        return None
    return action


def github_comments_url(since: datetime) -> str:
    encoded = urllib.parse.quote(since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
    return (
        f"https://api.github.com/repos/{REPOSITORY}/issues/{ISSUE_NUMBER}/comments"
        f"?since={encoded}&per_page=100"
    )


def fetch_comments(since: datetime, timeout_seconds: float = 20.0) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        github_comments_url(since),
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ReqSys-Desktop-Admin-Broker/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise BrokerError("resposta GitHub inválida")
    return [item for item in payload if isinstance(item, dict)]


def _is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _validate_checkout(source_root: Path, source_sha: str) -> Path:
    root = source_root.resolve()
    sha = validate_sha(source_sha)
    if not root.is_dir():
        raise BrokerError("source_root_invalid")

    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if completed.returncode != 0:
            raise BrokerError("source_checkout_invalid")
        return completed.stdout.strip()

    if git("rev-parse", "HEAD").casefold() != sha:
        raise BrokerError("source_sha_mismatch")
    if git("status", "--porcelain"):
        raise BrokerError("source_checkout_dirty")
    remote = git("remote", "get-url", "origin").replace("\\", "/").removesuffix(".git")
    accepted = {
        f"https://github.com/{REPOSITORY}".casefold(),
        f"ssh://git@github.com/{REPOSITORY}".casefold(),
        f"git@github.com:{REPOSITORY}".casefold(),
    }
    if remote.casefold() not in accepted:
        raise BrokerError("source_repository_mismatch")
    return root


def _validate_runner_root(runner_root: Path) -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise BrokerError("LOCALAPPDATA não definido")
    root = runner_root.resolve()
    allowed = (Path(local_app_data) / "ReqSys").resolve()
    try:
        root.relative_to(allowed)
    except ValueError:
        raise BrokerError("runner_root_outside_reqsys_runtime") from None
    if not (root / ".runner").is_file():
        raise BrokerError("runner_metadata_missing")
    return root


def _runner_service_name(runner_root: Path) -> str:
    marker = runner_root / ".service"
    if not marker.is_file():
        raise BrokerError("runner_service_marker_missing")
    service_name = marker.read_text(encoding="utf-8").strip()
    if RUNNER_SERVICE.fullmatch(service_name) is None:
        raise BrokerError("runner_service_name_invalid")
    return service_name


def _schedule_runner_restart(service_name: str, delay_seconds: int = 20) -> None:
    if not _is_admin():
        raise BrokerError("elevated_broker_required")
    if RUNNER_SERVICE.fullmatch(service_name) is None:
        raise BrokerError("runner_service_name_invalid")
    powershell = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    command = (
        f"Start-Sleep -Seconds {max(5, min(int(delay_seconds), 60))}; "
        f"Restart-Service -Name '{service_name}' -Force"
    )
    environment = os.environ.copy()
    environment["RUNNER_TRACKING_ID"] = ""
    creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    subprocess.Popen(
        [
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        env=environment,
        cwd=Path(os.environ.get("SystemRoot") or r"C:\Windows"),
        close_fds=True,
        creationflags=creation_flags,
    )


def fetch_comment_by_id(comment_id: int, timeout_seconds: float = 20.0) -> dict[str, Any]:
    if comment_id < 1:
        raise BrokerError("owner_comment_id_invalid")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/issues/comments/{comment_id}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ReqSys-Desktop-Admin-Broker/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise BrokerError("owner_comment_response_invalid")
    expected_issue = f"https://api.github.com/repos/{REPOSITORY}/issues/{ISSUE_NUMBER}"
    if str(payload.get("issue_url") or "").casefold() != expected_issue.casefold():
        raise BrokerError("owner_comment_issue_mismatch")
    return payload


def _load_module(path: Path, name: str):
    if not path.is_file():
        raise BrokerError(f"script governado ausente: {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise BrokerError(f"script governado não carregável: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def watchdog_runtime_metadata() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise BrokerError("LOCALAPPDATA não definido")
    return Path(base) / "ReqSys" / "DesktopControlPlaneWatchdog" / "metadata.json"


def _watchdog_module(metadata: dict[str, Any]):
    path = Path(metadata["release_root"]) / "scripts" / WATCHDOG_SCRIPT
    return _load_module(path, "reqsys_broker_watchdog")


def _ensure_watchdog_staged(metadata: dict[str, Any]) -> tuple[Any, Path]:
    target = watchdog_runtime_metadata()
    release_root = Path(metadata["release_root"])
    staged = _load_module(
        release_root / "scripts" / WATCHDOG_SCRIPT,
        "reqsys_broker_watchdog_stage",
    )
    if not target.is_file():
        result = staged.install(
            release_root,
            source_sha=metadata["source_sha"],
            python_executable=Path(sys.executable),
            runner_home=None,
            runtime_root=staged.default_runtime_root(),
            watch_interval_seconds=30,
            confirm=staged.CONFIRM,
        )
        if result.get("ok") is not True and result.get("activation_pending") is not True:
            raise BrokerError("watchdog não pôde ser preparado")
    if not target.is_file():
        raise BrokerError("metadata do watchdog não foi criada")
    return staged, target


def _activate_watchdog(metadata: dict[str, Any]) -> dict[str, Any]:
    _, target = _ensure_watchdog_staged(metadata)
    release_root = Path(metadata["release_root"])
    scripts = release_root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        launcher = _load_module(scripts / WATCHDOG_UAC_SCRIPT, "reqsys_broker_watchdog_launcher")
        result = launcher.launch(
            target,
            confirm=launcher.LAUNCH_CONFIRM,
            timeout_seconds=15,
        )
    finally:
        try:
            sys.path.remove(str(scripts))
        except ValueError:
            pass
    if result.get("ok") is not True:
        raise BrokerError("ativação governada do watchdog não concluiu")
    return {
        "handler": "activate-watchdog",
        "watchdog_result": result.get("result"),
        "task": result.get("task"),
    }


def _recover_runner(metadata: dict[str, Any]) -> dict[str, Any]:
    release_root = Path(metadata["release_root"])
    script = release_root / "scripts" / RUNNER_BOOTSTRAP_SCRIPT
    if not script.is_file():
        raise BrokerError("runner bootstrap governado ausente na release")

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--confirm",
            "ACTIVATE-DESKTOP-FREE-CONTROL-PLANE",
            "--repo-root",
            str(release_root),
            "--source-sha",
            validate_sha(str(metadata["source_sha"])),
            "--non-interactive-auth",
        ],
        cwd=release_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=420,
        check=False,
    )
    payload: dict[str, Any] = {}
    for line in reversed(completed.stdout.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break

    if not payload:
        raise BrokerError("runner_bootstrap_evidence_missing")
    state = str(payload.get("state") or "unknown")[:120]
    if completed.returncode != 0 or payload.get("ok") is not True:
        raise BrokerError(f"runner_bootstrap_failed:{state}")

    return {
        "handler": "recover-runner",
        "bootstrap_state": state,
        "runner_running": bool(payload.get("runner_running")),
        "runner_registry_present": bool(payload.get("runner_registry_present")),
        "runner_registry_status": str(payload.get("runner_registry_status") or "unknown")[:40],
        "runner_registry_labels_ok": bool(payload.get("runner_registry_labels_ok")),
        "runner_registered_now": bool(payload.get("runner_registered_now")),
        "runner_started_now": bool(payload.get("runner_started_now")),
    }


def _onboard_runner_runtime(metadata: dict[str, Any]) -> dict[str, Any]:
    if not _is_admin():
        raise BrokerError("elevated_broker_required")
    request = metadata.get("runner_onboard_request")
    if not isinstance(request, dict):
        raise BrokerError("runner_onboard_request_missing")

    owner_comment_id = int(request.get("owner_comment_id") or 0)
    source_sha = validate_sha(str(request.get("source_sha") or ""))
    comment = fetch_comment_by_id(owner_comment_id)
    action = authorize_comment(
        comment,
        not_before=parse_github_time(str(metadata["not_before"])),
        reference_time=now_utc(),
    )
    if action != RUNNER_ONBOARD_ACTION:
        raise BrokerError("owner_comment_not_authorized")

    source_root = _validate_checkout(Path(str(request.get("source_root") or "")), source_sha)
    runner_root = _validate_runner_root(Path(str(request.get("runner_root") or "")))
    runtime_root = Path(os.environ.get("SystemDrive") or "C:") / "ReqSysDev" / "Runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    program_data = Path(os.environ.get("ProgramData") or r"C:\ProgramData")
    manifest_path = program_data / "ReqSys" / "runner-pool.json"
    instance_seed = f"{REPOSITORY}|{socket.gethostname()}".encode("utf-8")
    instance_id = "reqsys-pc-" + hashlib.sha256(instance_seed).hexdigest()[:12]
    service_name = _runner_service_name(runner_root)
    powershell = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    installer = source_root / "scripts" / RUNNER_INSTALL_SCRIPT
    preflight = source_root / "scripts" / RUNNER_PREFLIGHT_SCRIPT
    policy = source_root / "config" / RUNNER_POOL_POLICY
    for required in (installer, preflight, policy):
        if not required.is_file():
            raise BrokerError(f"runner_onboard_file_missing:{required.name}")

    completed = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(installer),
            "-RunnerInstanceId",
            instance_id,
            "-RuntimeRoot",
            str(runtime_root),
            "-RunnerRoot",
            str(runner_root),
            "-Profile",
            "runtime",
            "-ManifestPath",
            str(manifest_path),
        ],
        cwd=source_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        check=False,
    )
    if completed.returncode != 0:
        raise BrokerError("runner_runtime_installer_blocked")

    preflight_result = subprocess.run(
        [
            sys.executable,
            str(preflight),
            "--policy",
            str(policy),
            "--manifest",
            str(manifest_path),
            "--profile",
            "runtime",
            "--repository",
            str(source_root),
        ],
        cwd=source_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    if preflight_result.returncode != 0:
        raise BrokerError("runner_post_install_preflight_blocked")

    _schedule_runner_restart(service_name)
    return {
        "handler": RUNNER_ONBOARD_ACTION,
        "profile": "runtime",
        "environment": "dev",
        "runner_instance_id": instance_id,
        "manifest_path": str(manifest_path),
        "admin_route": "scheduled_task_s4u_highest",
        "admin_secret_supplied": False,
        "labels_applied": False,
        "label_reconciliation_required": True,
        "service_restarted": False,
        "service_restart_scheduled": True,
        "canary_dispatched": False,
        "automatic_retry_enabled": False,
        "deploy_performed": False,
        "production_touched": False,
    }


def _recover_rdc(metadata: dict[str, Any], correlation_id: str) -> dict[str, Any]:
    release_root = Path(metadata["release_root"])
    script = release_root / "scripts" / RDC_RECOVERY_SCRIPT
    evidence = Path(metadata["runtime_root"]) / "evidence" / f"{correlation_id}.rdc.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--confirm",
            "RECOVER-GOVERNED-RDC",
            "--correlation-id",
            correlation_id,
            "--evidence-file",
            str(evidence),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    payload = json.loads(evidence.read_text(encoding="utf-8")) if evidence.is_file() else {}
    if completed.returncode != 0 or payload.get("ok") is not True:
        raise BrokerError("recuperação governada do RDC falhou")
    return {
        "handler": "recover-rdc",
        "mode": payload.get("mode"),
        "owner": payload.get("owner"),
        "fallback_armed": bool(payload.get("fallback_armed")),
    }


def _recover_control_plane(metadata: dict[str, Any]) -> dict[str, Any]:
    activation = _activate_watchdog(metadata)
    target = watchdog_runtime_metadata()
    installed = json.loads(target.read_text(encoding="utf-8"))
    watchdog = _watchdog_module(installed)
    cycle = watchdog.cycle(installed)
    return {
        "handler": "recover-control-plane",
        "activation": activation,
        "cycle": cycle,
    }


def _status(metadata: dict[str, Any]) -> dict[str, Any]:
    watchdog_state = {}
    target = watchdog_runtime_metadata()
    if target.is_file():
        installed = json.loads(target.read_text(encoding="utf-8"))
        state = Path(installed["runtime_root"]) / "state.json"
        if state.is_file():
            watchdog_state = json.loads(state.read_text(encoding="utf-8"))
    return {
        "handler": "status",
        "broker_task": task_status(),
        "watchdog_state": watchdog_state,
    }


def execute_action(action: str, metadata: dict[str, Any], comment_id: int) -> dict[str, Any]:
    correlation_id = f"desktop-admin-gh-comment-{comment_id}"
    if action == "status":
        result = _status(metadata)
    elif action == "recover-control-plane":
        result = _recover_control_plane(metadata)
    elif action == "recover-rdc":
        result = _recover_rdc(metadata, correlation_id)
    elif action == "recover-runner":
        result = _recover_runner(metadata)
    elif action == "activate-watchdog":
        result = _activate_watchdog(metadata)
    elif action == RUNNER_ONBOARD_ACTION:
        result = _onboard_runner_runtime(metadata)
    else:
        raise BrokerError("action_id não allowlisted")
    return {
        "ok": True,
        "action": action,
        "comment_id": comment_id,
        "correlation_id": correlation_id,
        "result": result,
        "production_touched": False,
        "secrets_read": False,
        "reboot_performed": False,
        "completed_at": now_iso(),
    }


def state_path(metadata: dict[str, Any]) -> Path:
    return Path(metadata["runtime_root"]) / "state.json"


def load_state(metadata: dict[str, Any]) -> dict[str, Any]:
    path = state_path(metadata)
    if not path.is_file():
        return {
            "last_seen_comment_id": 0,
            "last_seen_at": metadata["not_before"],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BrokerError("state inválido")
    return payload


def process_once(metadata: dict[str, Any], *, reference_time: datetime | None = None) -> dict[str, Any]:
    state = load_state(metadata)
    not_before = parse_github_time(metadata["not_before"])
    since = parse_github_time(str(state.get("last_seen_at") or metadata["not_before"]))
    last_seen = int(state.get("last_seen_comment_id") or 0)
    comments = sorted(fetch_comments(since), key=lambda item: int(item.get("id") or 0))
    accepted = 0
    for comment in comments:
        comment_id = int(comment.get("id") or 0)
        if comment_id <= last_seen:
            continue
        created = parse_github_time(str(comment.get("created_at") or metadata["not_before"]))
        action = authorize_comment(
            comment,
            not_before=not_before,
            reference_time=reference_time,
        )
        state["last_seen_comment_id"] = comment_id
        state["last_seen_at"] = created.isoformat()
        state["observed_at"] = now_iso()
        if action is None:
            atomic_json(state_path(metadata), state)
            last_seen = comment_id
            continue
        state["accepted"] = {
            "comment_id": comment_id,
            "action": action,
            "status": "inflight",
            "accepted_at": now_iso(),
        }
        atomic_json(state_path(metadata), state)
        try:
            outcome = execute_action(action, metadata, comment_id)
            state["accepted"] = {
                "comment_id": comment_id,
                "action": action,
                "status": "completed",
                "outcome": outcome,
            }
        except Exception as exc:
            state["accepted"] = {
                "comment_id": comment_id,
                "action": action,
                "status": "failed",
                "error": str(exc)[:1000],
                "error_type": type(exc).__name__,
            }
        state["observed_at"] = now_iso()
        atomic_json(state_path(metadata), state)
        accepted += 1
        last_seen = comment_id
    return {
        "ok": True,
        "comments_seen": len(comments),
        "commands_accepted": accepted,
        "last_seen_comment_id": last_seen,
    }


def watch(metadata_path: Path) -> int:
    metadata = load_installed_metadata(metadata_path)["metadata"]
    interval = max(30, min(int(metadata.get("poll_seconds") or DEFAULT_POLL_SECONDS), 300))
    while True:
        try:
            process_once(metadata)
        except Exception as exc:
            state = load_state(metadata)
            state["broker_error"] = {
                "error": str(exc)[:1000],
                "error_type": type(exc).__name__,
                "observed_at": now_iso(),
            }
            atomic_json(state_path(metadata), state)
        time.sleep(interval)


def current_user_id() -> str:
    import getpass
    return f"{socket.gethostname()}\\{getpass.getuser()}"


def _scheduler():
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise BrokerError("pywin32 indisponível") from exc
    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    return service


def register_task(*, python_executable: Path, launcher: Path) -> dict[str, Any]:
    require_windows_desktop()
    service = _scheduler()
    try:
        folder = service.GetFolder(TASK_FOLDER)
    except Exception:
        folder = service.GetFolder("\\").CreateFolder(TASK_FOLDER.lstrip("\\"))
    definition = service.NewTask(0)
    definition.RegistrationInfo.Description = "ReqSys Desktop privileged admin broker"
    definition.Settings.Enabled = True
    definition.Settings.StartWhenAvailable = True
    definition.Settings.MultipleInstances = TASK_INSTANCES_IGNORE_NEW
    definition.Settings.ExecutionTimeLimit = "PT0S"
    definition.Settings.RestartCount = 999
    definition.Settings.RestartInterval = "PT1M"
    trigger = definition.Triggers.Create(TASK_TRIGGER_BOOT)
    trigger.Enabled = True
    trigger.Delay = "PT30S"
    action = definition.Actions.Create(TASK_ACTION_EXEC)
    action.Path = str(python_executable)
    action.Arguments = f'"{launcher}"'
    action.WorkingDirectory = str(launcher.parent)
    principal = definition.Principal
    principal.UserId = current_user_id()
    principal.LogonType = TASK_LOGON_S4U
    principal.RunLevel = TASK_RUNLEVEL_HIGHEST
    try:
        folder.RegisterTaskDefinition(
            TASK_LEAF,
            definition,
            TASK_CREATE_OR_UPDATE,
            principal.UserId,
            None,
            TASK_LOGON_S4U,
        )
    except Exception as exc:
        detail = repr(exc).casefold()
        if "0x80070005" in detail or "-2147024891" in detail or "access is denied" in detail or "acesso negado" in detail:
            raise BrokerError("task_scheduler_access_denied") from exc
        raise BrokerError(f"registro do broker falhou: {type(exc).__name__}") from exc
    return {
        "ok": True,
        "task_name": TASK_NAME,
        "trigger": "AtStartup",
        "logon_type": "S4U",
        "run_level": "highest",
        "password_used": False,
    }


def task_status() -> dict[str, Any]:
    try:
        service = _scheduler()
        folder = service.GetFolder(TASK_FOLDER)
        task = folder.GetTask(TASK_LEAF)
        definition = task.Definition
        trigger_at_startup = any(
            definition.Triggers.Item(i).Type == TASK_TRIGGER_BOOT
            for i in range(1, definition.Triggers.Count + 1)
        )
        return {
            "exists": True,
            "trigger_at_startup": trigger_at_startup,
            "logon_type": "S4U" if definition.Principal.LogonType == TASK_LOGON_S4U else str(definition.Principal.LogonType),
            "run_level": "highest" if definition.Principal.RunLevel == TASK_RUNLEVEL_HIGHEST else str(definition.Principal.RunLevel),
            "enabled": bool(task.Enabled),
        }
    except Exception:
        return {"exists": False, "trigger_at_startup": False}


def run_task() -> dict[str, Any]:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    schtasks = root / "System32" / "schtasks.exe"
    completed = subprocess.run(
        [str(schtasks), "/Run", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        raise BrokerError("falha ao iniciar tarefa do broker")
    return {"run_returncode": completed.returncode}


def _restart_existing_task() -> dict[str, Any]:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    schtasks = root / "System32" / "schtasks.exe"
    subprocess.run(
        [str(schtasks), "/End", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    completed = subprocess.run(
        [str(schtasks), "/Run", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        raise BrokerError("admin_broker_task_restart_failed")
    return {"run_returncode": completed.returncode}


def stage_runner_onboard(
    source_root: Path,
    *,
    source_sha: str,
    runner_root: Path,
    owner_comment_id: int,
    confirm: str,
    timeout_seconds: int = 360,
) -> dict[str, Any]:
    if confirm != RUNNER_ONBOARD_STAGE_CONFIRM:
        raise BrokerError("runner_onboard_stage_confirmation_invalid")
    require_windows_desktop()
    contract = task_status()
    if not (
        contract.get("exists") is True
        and contract.get("trigger_at_startup") is True
        and contract.get("logon_type") == "S4U"
        and contract.get("run_level") == "highest"
        and contract.get("enabled") is True
    ):
        raise BrokerError("admin_broker_task_contract_invalid")

    sha = validate_sha(source_sha)
    source = _validate_checkout(source_root, sha)
    runner = _validate_runner_root(runner_root)
    comment = fetch_comment_by_id(owner_comment_id)
    created = parse_github_time(str(comment.get("created_at") or ""))
    action = authorize_comment(
        comment,
        not_before=created - timedelta(seconds=1),
        reference_time=now_utc(),
    )
    if action != RUNNER_ONBOARD_ACTION:
        raise BrokerError("owner_comment_not_authorized")

    runtime = default_runtime_root().resolve()
    installed_path = runtime / "metadata.json"
    installed = load_installed_metadata(installed_path)
    release = runtime / "releases" / sha
    _copy_release(source, release)
    _write_launcher(runtime)
    metadata = dict(installed["metadata"])
    metadata.update(
        {
            "source_sha": sha,
            "release_root": str(release),
            "python_executable": str(installed["python_executable"]),
            "not_before": created.isoformat(),
            "runner_onboard_request": {
                "source_root": str(source),
                "source_sha": sha,
                "runner_root": str(runner),
                "owner_comment_id": int(owner_comment_id),
            },
            "activation_pending": False,
            "requires_uac_activation": False,
            "production_touched": False,
            "secrets_read": False,
            "staged_at": now_iso(),
        }
    )
    atomic_json(installed_path, metadata)
    atomic_json(
        state_path(metadata),
        {
            "last_seen_comment_id": int(owner_comment_id) - 1,
            "last_seen_at": (created - timedelta(seconds=1)).isoformat(),
            "staged_owner_comment_id": int(owner_comment_id),
            "staged_at": now_iso(),
        },
    )
    restart = _restart_existing_task()

    deadline = time.monotonic() + max(30, min(int(timeout_seconds), 420))
    while time.monotonic() < deadline:
        state = load_state(metadata)
        accepted = state.get("accepted")
        if isinstance(accepted, dict) and int(accepted.get("comment_id") or 0) == int(owner_comment_id):
            status = str(accepted.get("status") or "")
            if status == "completed":
                outcome = accepted.get("outcome")
                if not isinstance(outcome, dict) or outcome.get("ok") is not True:
                    raise BrokerError("runner_onboard_evidence_invalid")
                return {
                    "ok": True,
                    "admin_route": "scheduled_task_s4u_highest",
                    "owner_comment_id": int(owner_comment_id),
                    "source_sha": sha,
                    "task_restart": restart,
                    "outcome": outcome,
                    "production_touched": False,
                    "admin_secret_supplied": False,
                }
            if status == "failed":
                error = str(accepted.get("error") or "unknown")[:300]
                raise BrokerError(f"runner_onboard_broker_failed:{error}")
        time.sleep(2)
    raise BrokerError("runner_onboard_broker_timeout")


def _copy_release(source_root: Path, release_root: Path) -> None:
    scripts = release_root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    for name in (
        "desktop_admin_broker.py",
        "desktop_admin_broker_uac_launcher.py",
        WATCHDOG_SCRIPT,
        WATCHDOG_UAC_SCRIPT,
        RDC_RECOVERY_SCRIPT,
        RUNNER_BOOTSTRAP_SCRIPT,
        RUNNER_INSTALL_SCRIPT,
        RUNNER_ONBOARD_SCRIPT,
        RUNNER_PREFLIGHT_SCRIPT,
    ):
        source = source_root / "scripts" / name
        if not source.is_file():
            raise BrokerError(f"script obrigatório ausente: {name}")
        destination = scripts / name
        destination.write_bytes(source.read_bytes())
    config = release_root / "config"
    config.mkdir(parents=True, exist_ok=True)
    policy = source_root / "config" / RUNNER_POOL_POLICY
    if not policy.is_file():
        raise BrokerError(f"arquivo obrigatório ausente: {RUNNER_POOL_POLICY}")
    (config / RUNNER_POOL_POLICY).write_bytes(policy.read_bytes())


def _write_launcher(runtime_root: Path) -> Path:
    launcher = runtime_root / "run.py"
    launcher.write_text(
        "from pathlib import Path\n"
        "import json, runpy, sys\n"
        "metadata = Path(__file__).with_name('metadata.json')\n"
        "payload = json.loads(metadata.read_text(encoding='utf-8'))\n"
        "script = Path(payload['release_root']) / 'scripts' / 'desktop_admin_broker.py'\n"
        "sys.argv = [str(script), 'watch', '--metadata', str(metadata)]\n"
        "runpy.run_path(str(script), run_name='__main__')\n",
        encoding="utf-8",
    )
    return launcher


def _write_uac_activation_launcher(
    runtime_root: Path,
    *,
    release_root: Path,
    python_executable: Path,
    metadata_path: Path,
) -> Path:
    launcher = runtime_root / "Activate-Desktop-Admin-Broker.cmd"
    uac_script = release_root / "scripts" / "desktop_admin_broker_uac_launcher.py"
    command = subprocess.list2cmdline(
        [
            str(python_executable),
            str(uac_script),
            "--metadata",
            str(metadata_path),
            "--confirm",
            "LAUNCH-DESKTOP-ADMIN-BROKER-UAC",
            "--timeout-seconds",
            "90",
        ]
    )
    launcher.write_text("@echo off\r\n" + command + "\r\n", encoding="utf-8")
    return launcher


def load_installed_metadata(metadata_path: Path, *, require_current_release: bool = False) -> dict[str, Any]:
    metadata_path = metadata_path.resolve()
    if not metadata_path.is_file():
        raise BrokerError("metadata do broker ausente")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    runtime_root = Path(str(metadata.get("runtime_root") or "")).resolve()
    release_root = Path(str(metadata.get("release_root") or "")).resolve()
    source_sha = validate_sha(str(metadata.get("source_sha") or ""))
    if metadata_path != runtime_root / "metadata.json":
        raise BrokerError("metadata fora do runtime governado")
    if os.name == "nt" and runtime_root != default_runtime_root().resolve():
        raise BrokerError("runtime_root fora do caminho governado")
    expected_release = runtime_root / "releases" / source_sha
    if release_root != expected_release:
        raise BrokerError("release_root não corresponde ao source_sha")
    release_broker = release_root / "scripts" / "desktop_admin_broker.py"
    launcher = runtime_root / "run.py"
    python_executable = Path(str(metadata.get("python_executable") or "")).resolve()
    for path in (release_broker, launcher, python_executable):
        if not path.is_file():
            raise BrokerError(f"arquivo instalado ausente: {path.name}")
    if require_current_release and release_broker.resolve() != Path(__file__).resolve():
        raise BrokerError("subcomando elevado deve executar da release imutável")
    return {
        "metadata": metadata,
        "metadata_path": metadata_path,
        "runtime_root": runtime_root,
        "release_root": release_root,
        "release_broker": release_broker,
        "launcher": launcher,
        "python_executable": python_executable,
    }


def register_task_from_metadata(metadata_path: Path) -> dict[str, Any]:
    installation = load_installed_metadata(metadata_path, require_current_release=True)
    return register_task(
        python_executable=installation["python_executable"],
        launcher=installation["launcher"],
    )


def install(
    source_root: Path,
    *,
    source_sha: str,
    python_executable: Path,
    runtime_root: Path | None,
    poll_seconds: int,
    confirm: str,
) -> dict[str, Any]:
    if confirm != INSTALL_CONFIRM:
        raise BrokerError("confirmação inválida")
    host = require_windows_desktop()
    sha = validate_sha(source_sha)
    runtime = (runtime_root or default_runtime_root()).resolve()
    release = runtime / "releases" / sha
    _copy_release(source_root.resolve(), release)
    launcher = _write_launcher(runtime)
    metadata_path = runtime / "metadata.json"
    activation_launcher = _write_uac_activation_launcher(
        runtime,
        release_root=release,
        python_executable=python_executable.resolve(),
        metadata_path=metadata_path,
    )
    metadata = {
        "schema_version": "1",
        "service": "reqsys-desktop-admin-broker",
        "host": host,
        "source_sha": sha,
        "runtime_root": str(runtime),
        "release_root": str(release),
        "python_executable": str(python_executable.resolve()),
        "poll_seconds": max(30, min(int(poll_seconds), 300)),
        "not_before": now_iso(),
        "repository": REPOSITORY,
        "issue_number": ISSUE_NUMBER,
        "expected_actor": EXPECTED_ACTOR,
        "activation_pending": False,
        "requires_uac_activation": False,
        "production_touched": False,
        "secrets_read": False,
        "installed_at": now_iso(),
        "activation_launcher": str(activation_launcher),
    }
    runtime.mkdir(parents=True, exist_ok=True)
    atomic_json(metadata_path, metadata)
    activation_pending = False
    try:
        task = register_task(python_executable=python_executable.resolve(), launcher=launcher)
    except BrokerError as exc:
        if str(exc) != "task_scheduler_access_denied":
            raise
        activation_pending = True
        task = {"exists": False, "error": "access_denied"}
        metadata.update(
            {
                "activation_pending": True,
                "requires_uac_activation": True,
            }
        )
        atomic_json(metadata_path, metadata)
    started = None
    if not activation_pending:
        started = run_task()
    return {
        "ok": True,
        "activation_pending": activation_pending,
        "requires_uac_activation": activation_pending,
        "task": task,
        "start": started,
        "metadata_path": str(metadata_path),
        "activation_launcher": str(activation_launcher),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    install_p = sub.add_parser("install")
    install_p.add_argument("--source-root", type=Path, required=True)
    install_p.add_argument("--source-sha", required=True)
    install_p.add_argument("--python-executable", type=Path, default=Path(sys.executable))
    install_p.add_argument("--runtime-root", type=Path)
    install_p.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    install_p.add_argument("--confirm", required=True)

    watch_p = sub.add_parser("watch")
    watch_p.add_argument("--metadata", type=Path, required=True)

    once_p = sub.add_parser("once")
    once_p.add_argument("--metadata", type=Path, required=True)

    register_p = sub.add_parser("register-task-com")
    register_p.add_argument("--metadata", type=Path, required=True)

    onboard_p = sub.add_parser("stage-runner-onboard")
    onboard_p.add_argument("--source-root", type=Path, required=True)
    onboard_p.add_argument("--source-sha", required=True)
    onboard_p.add_argument("--runner-root", type=Path, required=True)
    onboard_p.add_argument("--owner-comment-id", type=int, required=True)
    onboard_p.add_argument("--confirm", required=True)
    onboard_p.add_argument("--timeout-seconds", type=int, default=360)

    args = parser.parse_args()
    try:
        if args.command == "install":
            payload = install(
                args.source_root,
                source_sha=args.source_sha,
                python_executable=args.python_executable,
                runtime_root=args.runtime_root,
                poll_seconds=args.poll_seconds,
                confirm=args.confirm,
            )
        elif args.command == "watch":
            return watch(args.metadata.resolve())
        elif args.command == "once":
            metadata = load_installed_metadata(args.metadata.resolve())["metadata"]
            payload = process_once(metadata)
        elif args.command == "stage-runner-onboard":
            payload = stage_runner_onboard(
                args.source_root,
                source_sha=args.source_sha,
                runner_root=args.runner_root,
                owner_comment_id=args.owner_comment_id,
                confirm=args.confirm,
                timeout_seconds=args.timeout_seconds,
            )
        else:
            payload = register_task_from_metadata(args.metadata.resolve())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:1000], "error_type": type(exc).__name__}, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
