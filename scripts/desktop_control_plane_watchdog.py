#!/usr/bin/env python3
"""Supervisor autônomo do plano de controle local do Desktop PC24x7.

Objetivo:
- recuperar RDC e GitHub Actions runner sem depender de nenhum dos dois;
- iniciar no boot via tarefa Windows S4U;
- manter evidência local sanitizada;
- não ler nem registrar segredos do runner/RDC;
- operar somente em DESKTOP-PDQK954 e local/DEV.
"""
from __future__ import annotations

import argparse
import json
import locale
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
SERVICE_NAME = "reqsys-desktop-control-plane-watchdog"
TASK_FOLDER = r"\Automation"
TASK_LEAF = "ReqSysDesktopControlPlaneWatchdog"
TASK_NAME = TASK_FOLDER + "\\" + TASK_LEAF
TASK_TRIGGER_BOOT = 8
TASK_ACTION_EXEC = 0
TASK_LOGON_S4U = 2
TASK_CREATE_OR_UPDATE = 6
TASK_RUNLEVEL_LUA = 0
TASK_INSTANCES_IGNORE_NEW = 2
CONFIRM = "INSTALL-DESKTOP-CONTROL-PLANE-WATCHDOG"

RDC_RECOVERY_CONFIRM = "RECOVER-GOVERNED-RDC"
RDC_RECOVERY_SCRIPT = "pc24x7_rdc_recovery.py"
UAC_LAUNCHER_SCRIPT = "desktop_control_plane_watchdog_uac_launcher.py"
RDC_HEADLESS_CLAIM = Path(r"C:\ProgramData\ReqSys\RdcSvc\rdc-headless-owner.json")
RDC_CLAIM_MAX_AGE_SECONDS = 20.0

RUNNER_PROCESS = "Runner.Listener.exe"
RUNNER_REQUIRED = ((".runner",), ("run.cmd",), ("bin", "Runner.Listener.exe"))
DEFAULT_WATCH_SECONDS = 30
RUNNER_START_TIMEOUT_SECONDS = 30
RDC_RECOVERY_TIMEOUT_SECONDS = 60


class WatchdogError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_windows_desktop() -> str:
    if os.name != "nt":
        raise WatchdogError("Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise WatchdogError(f"host não autorizado: {host}")
    return host


def default_runtime_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise WatchdogError("LOCALAPPDATA não definido")
    return Path(local) / "ReqSys" / "DesktopControlPlaneWatchdog"


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=True, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _candidate_runner_homes() -> list[Path]:
    candidates = [
        Path(r"C:\actions-runner"),
        Path(r"C:\dev\actions-runner"),
        Path(r"C:\dev\github-actions-runner"),
        Path(r"C:\dev\runner"),
    ]
    configured = os.environ.get("REQSYS_GITHUB_RUNNER_HOME")
    if configured:
        candidates.insert(0, Path(configured))
    dev = Path(r"C:\dev")
    if dev.is_dir():
        try:
            for item in dev.iterdir():
                if item.is_dir() and "runner" in item.name.casefold():
                    candidates.append(item)
        except OSError:
            return candidates
    return candidates


def validate_runner_home(path: Path) -> Path:
    resolved = path.resolve()
    missing = ["/".join(parts) for parts in RUNNER_REQUIRED if not resolved.joinpath(*parts).is_file()]
    if missing:
        raise WatchdogError("runner_home inválido; arquivos ausentes: " + ", ".join(missing))
    return resolved


def discover_runner_home(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return validate_runner_home(explicit)
    seen: set[str] = set()
    for candidate in _candidate_runner_homes():
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        try:
            return validate_runner_home(candidate)
        except (WatchdogError, OSError):
            continue
    raise WatchdogError(
        "GitHub Actions runner não localizado; informe --runner-home uma única vez na instalação"
    )


def _tasklist(image: str) -> subprocess.CompletedProcess[str]:
    system_root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    tasklist = system_root / "System32" / "tasklist.exe"
    return subprocess.run(
        [str(tasklist), "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False) or "utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )


def runner_running() -> bool:
    if os.name != "nt":
        return False
    result = _tasklist(RUNNER_PROCESS)
    return result.returncode == 0 and RUNNER_PROCESS.casefold() in result.stdout.casefold()


def _creationflags() -> int:
    if os.name != "nt":
        return 0
    return (
        subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NO_WINDOW
    )


def start_runner(runner_home: Path, log_path: Path) -> dict[str, Any]:
    runner_home = validate_runner_home(runner_home)
    if runner_running():
        return {"status": "healthy", "started": False}

    system_root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    cmd = system_root / "System32" / "cmd.exe"
    run_cmd = runner_home / "run.cmd"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("a", encoding="utf-8", buffering=1)
    try:
        process = subprocess.Popen(
            [str(cmd), "/d", "/s", "/c", str(run_cmd)],
            cwd=str(runner_home),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=_creationflags(),
        )
    finally:
        log_handle.close()

    deadline = time.monotonic() + RUNNER_START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if runner_running():
            return {"status": "recovered", "started": True, "launcher_pid": process.pid}
        if process.poll() is not None:
            raise WatchdogError(f"runner terminou durante startup: exit={process.returncode}")
        time.sleep(1)

    raise WatchdogError("timeout aguardando Runner.Listener.exe")


def read_rdc_claim() -> dict[str, Any]:
    if not RDC_HEADLESS_CLAIM.is_file():
        return {"fresh": False, "reason": "claim_missing"}
    try:
        payload = json.loads(RDC_HEADLESS_CLAIM.read_text(encoding="utf-8"))
        if payload.get("ready") is not True:
            return {"fresh": False, "reason": "claim_not_ready"}
        raw_updated = str(payload.get("updated_at") or "")
        updated = datetime.fromisoformat(raw_updated.replace("Z", "+00:00"))
        if updated.tzinfo is None:
            raise ValueError("updated_at sem timezone")
        age = (datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds()
        fresh = 0 <= age <= RDC_CLAIM_MAX_AGE_SECONDS
        return {
            "fresh": fresh,
            "reason": "fresh" if fresh else "claim_stale",
            "age_seconds": round(age, 3),
            "ready": True,
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"fresh": False, "reason": "claim_invalid", "error_type": type(exc).__name__}


def recover_rdc(*, python_executable: Path, recovery_script: Path, evidence_path: Path) -> dict[str, Any]:
    claim = read_rdc_claim()
    if claim.get("fresh"):
        return {"status": "healthy", "recovered": False, "claim": claim}

    correlation_id = f"desktop-watchdog-rdc-{int(time.time())}"
    completed = subprocess.run(
        [
            str(python_executable),
            str(recovery_script),
            "--confirm",
            RDC_RECOVERY_CONFIRM,
            "--correlation-id",
            correlation_id,
            "--evidence-file",
            str(evidence_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=RDC_RECOVERY_TIMEOUT_SECONDS,
        check=False,
    )
    evidence: dict[str, Any] = {}
    if evidence_path.is_file():
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            evidence = {}
    if completed.returncode != 0 or evidence.get("ok") is not True:
        raise WatchdogError(
            "recuperação RDC falhou: "
            + str(evidence.get("error") or completed.stderr or completed.stdout)[-500:]
        )
    return {
        "status": "recovered",
        "recovered": True,
        "mode": evidence.get("mode"),
        "owner": evidence.get("owner"),
        "fallback_armed": bool(evidence.get("fallback_armed")),
    }


def cycle(metadata: dict[str, Any]) -> dict[str, Any]:
    host = require_windows_desktop()
    runtime_root = Path(metadata["runtime_root"])
    release_root = Path(metadata["release_root"])
    runner_home = validate_runner_home(Path(metadata["runner_home"]))
    python_executable = Path(metadata["python_executable"])
    recovery_script = release_root / "scripts" / RDC_RECOVERY_SCRIPT
    if not recovery_script.is_file():
        raise WatchdogError("script de recuperação RDC ausente na release")

    rdc = recover_rdc(
        python_executable=python_executable,
        recovery_script=recovery_script,
        evidence_path=runtime_root / "evidence" / "rdc-recovery-last.json",
    )
    runner = start_runner(runner_home, runtime_root / "logs" / "github-runner.log")
    payload = {
        "schema_version": "1",
        "service": SERVICE_NAME,
        "host": host,
        "source_sha": metadata["source_sha"],
        "generated_at": now_iso(),
        "rdc": rdc,
        "github_runner": runner,
        "ok": True,
        "production_touched": False,
        "secrets_read": False,
        "reboot_performed": False,
    }
    atomic_json(runtime_root / "state.json", payload)
    return payload


def _acquire_watch_lock(runtime_root: Path):
    path = runtime_root / "watchdog.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    if os.name == "nt":
        import msvcrt
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            raise WatchdogError("outro watchdog já está ativo") from exc
    return handle


def watch(metadata_path: Path) -> int:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    runtime_root = Path(metadata["runtime_root"])
    interval = max(10, int(metadata.get("watch_interval_seconds") or DEFAULT_WATCH_SECONDS))
    lock_handle = _acquire_watch_lock(runtime_root)
    try:
        while True:
            try:
                cycle(metadata)
            except Exception as exc:
                atomic_json(
                    runtime_root / "state.json",
                    {
                        "schema_version": "1",
                        "service": SERVICE_NAME,
                        "host": socket.gethostname(),
                        "source_sha": metadata.get("source_sha"),
                        "generated_at": now_iso(),
                        "ok": False,
                        "error": str(exc)[:1000],
                        "error_type": type(exc).__name__,
                        "production_touched": False,
                        "secrets_read": False,
                        "reboot_performed": False,
                    },
                )
            time.sleep(interval)
    finally:
        lock_handle.close()


def _copy_release(source_root: Path, release_root: Path) -> None:
    scripts = release_root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), scripts / Path(__file__).name)
    for required_name in (RDC_RECOVERY_SCRIPT, UAC_LAUNCHER_SCRIPT):
        required = source_root / "scripts" / required_name
        if not required.is_file():
            raise WatchdogError(f"script obrigatório ausente: {required}")
        shutil.copy2(required, scripts / required_name)


def _write_launcher(runtime_root: Path) -> Path:
    launcher = runtime_root / "run.py"
    launcher.write_text(
        "from pathlib import Path\n"
        "import json, runpy, sys\n"
        "metadata = Path(__file__).with_name('metadata.json')\n"
        "payload = json.loads(metadata.read_text(encoding='utf-8'))\n"
        "script = Path(payload['release_root']) / 'scripts' / 'desktop_control_plane_watchdog.py'\n"
        "sys.argv = [str(script), 'watch', '--metadata', str(metadata)]\n"
        "runpy.run_path(str(script), run_name='__main__')\n",
        encoding="utf-8",
    )
    return launcher


def load_installed_metadata(
    metadata_path: Path,
    *,
    require_current_release: bool = False,
) -> dict[str, Any]:
    metadata_path = metadata_path.resolve()
    if not metadata_path.is_file():
        raise WatchdogError("metadata do watchdog ausente")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    runtime_root = Path(str(metadata.get("runtime_root") or "")).resolve()
    release_root = Path(str(metadata.get("release_root") or "")).resolve()
    python_executable = Path(str(metadata.get("python_executable") or "")).resolve()
    source_sha = str(metadata.get("source_sha") or "")
    if metadata_path != runtime_root / "metadata.json":
        raise WatchdogError("metadata fora do runtime governado")
    if len(source_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in source_sha):
        raise WatchdogError("source_sha da instalação inválido")
    expected_release = runtime_root / "releases" / source_sha.lower()
    if release_root != expected_release:
        raise WatchdogError("release_root não corresponde ao source_sha governado")
    if str(metadata.get("host") or "").casefold() != EXPECTED_HOST.casefold():
        raise WatchdogError("metadata pertence a host não autorizado")
    if os.name == "nt" and runtime_root != default_runtime_root().resolve():
        raise WatchdogError("runtime_root fora do caminho governado do Desktop")
    release_watchdog = release_root / "scripts" / "desktop_control_plane_watchdog.py"
    launcher = runtime_root / "run.py"
    for path, label in (
        (release_watchdog, "watchdog instalado"),
        (python_executable, "Python instalado"),
        (launcher, "launcher estável"),
    ):
        if not path.is_file():
            raise WatchdogError(f"{label} ausente: {path}")
    if require_current_release and release_watchdog.resolve() != Path(__file__).resolve():
        raise WatchdogError("subcomando elevado deve executar da release imutável instalada")
    return {
        "metadata": metadata,
        "metadata_path": metadata_path,
        "runtime_root": runtime_root,
        "release_root": release_root,
        "release_watchdog": release_watchdog,
        "python_executable": python_executable,
        "launcher": launcher,
        "source_sha": source_sha.lower(),
    }


def register_task_from_metadata(metadata_path: Path) -> dict[str, Any]:
    installation = load_installed_metadata(metadata_path, require_current_release=True)
    return register_boot_task(
        python_executable=installation["python_executable"],
        launcher=installation["launcher"],
    )


def current_user_id() -> str:
    import getpass
    return f"{socket.gethostname()}\\{getpass.getuser()}"


def register_boot_task(*, python_executable: Path, launcher: Path) -> dict[str, Any]:
    require_windows_desktop()
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise WatchdogError("pywin32 indisponível para registrar tarefa AtStartup") from exc

    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    try:
        folder = service.GetFolder(TASK_FOLDER)
    except Exception:
        root = service.GetFolder("\\")
        folder = root.CreateFolder(TASK_FOLDER.lstrip("\\"))

    definition = service.NewTask(0)
    definition.RegistrationInfo.Description = (
        "ReqSys Desktop control-plane watchdog: RDC + GitHub Actions runner"
    )
    definition.Settings.Enabled = True
    definition.Settings.StartWhenAvailable = True
    definition.Settings.DisallowStartIfOnBatteries = False
    definition.Settings.StopIfGoingOnBatteries = False
    definition.Settings.MultipleInstances = TASK_INSTANCES_IGNORE_NEW
    definition.Settings.ExecutionTimeLimit = "PT0S"
    restart_policy_supported = True
    try:
        definition.Settings.RestartCount = 999
        definition.Settings.RestartInterval = "PT1M"
    except Exception:
        restart_policy_supported = False

    trigger = definition.Triggers.Create(TASK_TRIGGER_BOOT)
    trigger.Enabled = True
    trigger.Delay = "PT20S"

    action = definition.Actions.Create(TASK_ACTION_EXEC)
    action.Path = str(python_executable)
    action.Arguments = f'"{launcher}"'
    action.WorkingDirectory = str(launcher.parent)

    principal = definition.Principal
    principal.UserId = current_user_id()
    principal.LogonType = TASK_LOGON_S4U
    principal.RunLevel = TASK_RUNLEVEL_LUA

    try:
        folder.RegisterTaskDefinition(
            TASK_LEAF,
            definition,
            TASK_CREATE_OR_UPDATE,
            principal.UserId,
            "",
            TASK_LOGON_S4U,
        )
    except Exception as exc:
        detail = repr(exc).casefold()
        if (
            "-2147024891" in detail
            or "0x80070005" in detail
            or "access is denied" in detail
            or "acesso negado" in detail
        ):
            raise WatchdogError("task_scheduler_access_denied") from exc
        raise WatchdogError(f"registro AtStartup falhou: {type(exc).__name__}") from exc

    return {
        "ok": True,
        "task_name": TASK_NAME,
        "trigger": "AtStartup",
        "logon_type": "S4U",
        "password_used": False,
        "run_level": "limited",
        "restart_policy_supported": restart_policy_supported,
    }


def _schtasks() -> Path:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    target = root / "System32" / "schtasks.exe"
    if not target.is_file():
        raise WatchdogError("schtasks.exe não encontrado")
    return target


def run_watchdog_task() -> dict[str, Any]:
    completed = subprocess.run(
        [str(_schtasks()), "/Run", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False) or "utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        raise WatchdogError("tarefa watchdog não pôde ser iniciada")
    return {"run_returncode": completed.returncode}


def task_status() -> dict[str, Any]:
    if os.name != "nt":
        return {"exists": False, "trigger_at_startup": False}
    completed = subprocess.run(
        [str(_schtasks()), "/Query", "/TN", TASK_NAME, "/XML"],
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False) or "utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        return {"exists": False, "trigger_at_startup": False}
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(completed.stdout)
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        boot = root.find(".//t:BootTrigger", ns) is not None
        logon_type = root.findtext(".//t:Principal/t:LogonType", default="", namespaces=ns)
    except Exception as exc:
        return {
            "exists": True,
            "trigger_at_startup": False,
            "parse_error": type(exc).__name__,
        }
    return {
        "exists": True,
        "trigger_at_startup": boot,
        "task_name": TASK_NAME,
        "logon_type": logon_type,
    }


def install(
    source_root: Path,
    *,
    source_sha: str,
    python_executable: Path,
    runner_home: Path | None,
    runtime_root: Path,
    watch_interval_seconds: int,
    confirm: str,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise WatchdogError("confirmação inválida")
    host = require_windows_desktop()
    if len(source_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in source_sha):
        raise WatchdogError("source_sha inválido")
    source_root = source_root.resolve()
    discovered_runner = discover_runner_home(runner_home)
    release_root = runtime_root / "releases" / source_sha.lower()
    _copy_release(source_root, release_root)
    launcher = _write_launcher(runtime_root)

    metadata = {
        "schema_version": "1",
        "service": SERVICE_NAME,
        "host": host,
        "source_sha": source_sha.lower(),
        "runtime_root": str(runtime_root),
        "release_root": str(release_root),
        "python_executable": str(python_executable.resolve()),
        "runner_home": str(discovered_runner),
        "watch_interval_seconds": max(10, int(watch_interval_seconds)),
        "installed_at": now_iso(),
        "production_touched": False,
        "secrets_read": False,
    }
    metadata_path = runtime_root / "metadata.json"
    atomic_json(metadata_path, metadata)
    activation_pending = False
    requires_uac_activation = False
    try:
        task = register_boot_task(
            python_executable=python_executable.resolve(),
            launcher=launcher,
        )
        started = run_watchdog_task()
        headless_boot_ready = bool(
            task.get("trigger") == "AtStartup"
            and str(task.get("logon_type") or "").casefold() == "s4u"
        )
    except WatchdogError as exc:
        if str(exc) != "task_scheduler_access_denied":
            raise
        task = task_status()
        started = {"started": False, "reason": "uac_activation_required"}
        headless_boot_ready = False
        activation_pending = True
        requires_uac_activation = True

    result = {
        "ok": True,
        "host": host,
        "service": SERVICE_NAME,
        "source_sha": source_sha.lower(),
        "runtime_root": str(runtime_root),
        "runner_home": str(discovered_runner),
        "task": task,
        "start": started,
        "headless_boot_ready": headless_boot_ready,
        "activation_pending": activation_pending,
        "requires_uac_activation": requires_uac_activation,
        "uac_launcher": str(release_root / "scripts" / UAC_LAUNCHER_SCRIPT),
        "production_touched": False,
        "secrets_read": False,
        "reboot_performed": False,
        "installed_at": now_iso(),
    }
    atomic_json(runtime_root / "install-evidence.json", result)
    return result


def status(runtime_root: Path) -> dict[str, Any]:
    state: dict[str, Any] = {}
    state_path = runtime_root / "state.json"
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {"ok": False, "error": "state_invalid"}
    return {
        "host": socket.gethostname(),
        "task": task_status(),
        "state": state,
        "metadata_present": (runtime_root / "metadata.json").is_file(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    install_parser = sub.add_parser("install")
    install_parser.add_argument("--source-root", type=Path, required=True)
    install_parser.add_argument("--source-sha", required=True)
    install_parser.add_argument("--python-executable", type=Path, default=Path(sys.executable))
    install_parser.add_argument("--runner-home", type=Path)
    install_parser.add_argument("--runtime-root", type=Path, default=None)
    install_parser.add_argument("--watch-interval-seconds", type=int, default=DEFAULT_WATCH_SECONDS)
    install_parser.add_argument("--confirm", required=True)

    watch_parser = sub.add_parser("watch")
    watch_parser.add_argument("--metadata", type=Path, required=True)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--runtime-root", type=Path, default=None)

    register_parser = sub.add_parser("register-task-com")
    register_parser.add_argument("--metadata", type=Path, required=True)

    ns = parser.parse_args()
    try:
        if ns.command == "install":
            runtime_root = ns.runtime_root or default_runtime_root()
            payload = install(
                ns.source_root,
                source_sha=ns.source_sha,
                python_executable=ns.python_executable,
                runner_home=ns.runner_home,
                runtime_root=runtime_root,
                watch_interval_seconds=ns.watch_interval_seconds,
                confirm=ns.confirm,
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 0
        if ns.command == "watch":
            return watch(ns.metadata)
        if ns.command == "status":
            runtime_root = ns.runtime_root or default_runtime_root()
            print(json.dumps(status(runtime_root), ensure_ascii=False, sort_keys=True))
            return 0
        if ns.command == "register-task-com":
            payload = register_task_from_metadata(ns.metadata)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 0
        raise WatchdogError("comando inválido")
    except (WatchdogError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc)[:1000],
                    "error_type": type(exc).__name__,
                    "production_touched": False,
                    "secrets_read": False,
                    "reboot_performed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
