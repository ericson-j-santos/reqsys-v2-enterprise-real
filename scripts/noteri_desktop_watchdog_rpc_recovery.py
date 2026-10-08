#!/usr/bin/env python3
"""Consulta e inicia localmente a tarefa watchdog já existente do Desktop."""
from __future__ import annotations

import argparse
import importlib.util
import json
import locale
import os
import socket
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

TARGET_HOST = "DESKTOP-PDQK954"
EXPECTED_SOURCE_HOST = TARGET_HOST
TASK_NAME = r"\Automation\ReqSysDesktopControlPlaneWatchdog"
CONFIRM = "RUN-EXISTING-DESKTOP-WATCHDOG"
TASK_LOGON_S4U = "S4U"
CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
TaskRepair = Callable[[], dict[str, Any]]


class RecoveryError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())[:limit]


def require_desktop(host: str | None = None, platform: str | None = None) -> None:
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise RecoveryError(f"host_origem_nao_autorizado:{actual_host}")
    if actual_platform != "nt":
        raise RecoveryError("windows_required")


def schtasks_executable() -> Path:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    path = root / "System32" / "schtasks.exe"
    if not path.is_file():
        raise RecoveryError("schtasks_not_found")
    return path


def default_run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False) or "utf-8",
        errors="replace",
        timeout=25,
        check=False,
    )


def parse_task_xml(xml_text: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RecoveryError("task_xml_invalid") from exc
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    enabled = root.findtext(
        ".//t:Settings/t:Enabled",
        default="true",
        namespaces=ns,
    )
    return {
        "exists": True,
        "enabled": str(enabled or "true").strip().casefold() == "true",
        "trigger_at_startup": root.find(".//t:BootTrigger", ns) is not None,
        "logon_type": root.findtext(
            ".//t:Principal/t:LogonType",
            default="",
            namespaces=ns,
        ),
    }


def query_task(run_cmd: CommandRunner) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None]:
    completed = run_cmd(
        [
            str(schtasks_executable()),
            "/Query",
            "/TN",
            TASK_NAME,
            "/XML",
        ]
    )
    if completed.returncode != 0:
        return completed, None
    return completed, parse_task_xml(completed.stdout)


def request_task_run(run_cmd: CommandRunner) -> subprocess.CompletedProcess[str]:
    return run_cmd(
        [
            str(schtasks_executable()),
            "/Run",
            "/TN",
            TASK_NAME,
        ]
    )


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def repair_watchdog_task(source_sha: str, *, allow_uac: bool = False, uac_confirm: str = "") -> dict[str, Any]:
    if len(source_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in source_sha):
        raise RecoveryError("source_sha_invalid")
    source_root = Path(__file__).resolve().parents[1]
    module_path = source_root / "scripts" / "desktop_control_plane_watchdog.py"
    spec = importlib.util.spec_from_file_location("reqsys_desktop_watchdog_repair", module_path)
    if spec is None or spec.loader is None:
        raise RecoveryError("watchdog_module_unavailable")
    watchdog = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(watchdog)

    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RecoveryError("localappdata_missing")
    runtime_root = Path(local) / "ReqSys" / "DesktopControlPlaneWatchdog"
    python_executable = runtime_root / "python" / "3.12.10" / "python.exe"
    runner_home = Path(local) / "ReqSys" / "Pc24x7GitHubRunner"
    if not python_executable.is_file():
        raise RecoveryError("persistent_watchdog_python_missing")

    version = subprocess.run(
        [str(python_executable), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    observed_version = sanitize(version.stdout or version.stderr)
    if version.returncode != 0 or observed_version != "Python 3.12.10":
        raise RecoveryError("persistent_watchdog_python_version_mismatch")

    installed = watchdog.install(
        source_root,
        source_sha=source_sha,
        python_executable=python_executable,
        runner_home=runner_home,
        runtime_root=runtime_root,
        watch_interval_seconds=30,
        confirm=watchdog.CONFIRM,
    )
    activation_mode = ""
    if installed.get("headless_boot_ready") is not True and installed.get(
        "requires_uac_activation"
    ):
        if not allow_uac:
            raise RecoveryError("watchdog_task_repair_requires_uac")
        launcher_path = source_root / "scripts" / "desktop_control_plane_watchdog_uac_launcher.py"
        launcher_spec = importlib.util.spec_from_file_location(
            "reqsys_desktop_watchdog_uac_activation",
            launcher_path,
        )
        if launcher_spec is None or launcher_spec.loader is None:
            raise RecoveryError("watchdog_uac_launcher_unavailable")
        launcher = importlib.util.module_from_spec(launcher_spec)
        launcher_spec.loader.exec_module(launcher)
        activated = launcher.launch(
            runtime_root / "metadata.json",
            confirm=uac_confirm,
            timeout_seconds=120,
        )
        if activated.get("ok") is not True:
            raise RecoveryError("watchdog_uac_approval_or_provisioning_pending")
        installed["headless_boot_ready"] = True
        installed["activation_pending"] = False
        activation_mode = str(activated.get("mode") or "uac")
    if installed.get("headless_boot_ready") is not True:
        raise RecoveryError("watchdog_task_repair_not_ready")
    return {
        "headless_boot_ready": True,
        "registration_method": activation_mode
        or str((installed.get("task") or {}).get("registration_method") or ""),
        "activation_pending": bool(installed.get("activation_pending")),
        "uac_activation_mode": activation_mode,
    }


def query_reports_missing_task(completed: subprocess.CompletedProcess[str]) -> bool:
    if completed.returncode == 0:
        return False
    detail = sanitize(completed.stderr or completed.stdout).casefold()
    return any(
        marker in detail
        for marker in (
            "cannot find the file specified",
            "não pode encontrar o arquivo especificado",
            "nao pode encontrar o arquivo especificado",
            "encontrar o arquivo especificado",
            "task does not exist",
            "not found",
        )
    )


def recover(
    *,
    confirm: str,
    evidence_file: Path,
    run_cmd: CommandRunner = default_run,
    repair: TaskRepair | None = None,
    source_host: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    if confirm != CONFIRM:
        raise RecoveryError("confirmation_invalid")
    require_desktop(source_host, platform)

    query, task = query_task(run_cmd)
    initial_query_returncode = int(query.returncode)
    repair_attempted = False
    repair_summary: dict[str, Any] = {}
    repair_error = ""
    if query_reports_missing_task(query) and repair is not None:
        repair_attempted = True
        try:
            repair_summary = repair()
        except Exception as exc:
            repair_error = sanitize(f"{type(exc).__name__}:{exc}")
        if not repair_error:
            query, task = query_task(run_cmd)
    payload: dict[str, Any] = {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "source_host": EXPECTED_SOURCE_HOST,
        "target_host": TARGET_HOST,
        "execution_mode": "local_pc24x7_runner",
        "remote_access_attempted": False,
        "rdc_required": False,
        "task_name": TASK_NAME,
        "query_returncode": int(query.returncode),
        "initial_query_returncode": initial_query_returncode,
        "task": task,
        "run_requested": False,
        "production_touched": False,
        "secrets_read": False,
        "credentials_supplied": False,
        "task_created_or_modified": bool(repair_attempted and not repair_error),
        "task_repair_attempted": repair_attempted,
        "task_repair_verified": bool(repair_attempted and not repair_error and task is not None),
        "task_repair": repair_summary,
    }

    if repair_error:
        payload.update(
            {
                "ok": False,
                "result": "DESKTOP_WATCHDOG_TASK_REPAIR_BLOCKED",
                "repair_error": repair_error,
            }
        )
        write_evidence(evidence_file, payload)
        return payload

    if query.returncode != 0 or task is None:
        payload.update(
            {
                "ok": False,
                "result": "DESKTOP_WATCHDOG_QUERY_BLOCKED",
                "query_error": sanitize(query.stderr or query.stdout),
            }
        )
        write_evidence(evidence_file, payload)
        return payload

    if (
        task.get("enabled") is not True
        or not task.get("trigger_at_startup")
        or str(task.get("logon_type") or "").casefold() != TASK_LOGON_S4U.casefold()
    ):
        payload.update(
            {
                "ok": False,
                "result": "DESKTOP_WATCHDOG_CONFIGURATION_NOT_READY",
            }
        )
        write_evidence(evidence_file, payload)
        return payload

    requested = request_task_run(run_cmd)
    payload["run_returncode"] = int(requested.returncode)
    if requested.returncode != 0:
        payload.update(
            {
                "ok": False,
                "result": "DESKTOP_WATCHDOG_RUN_BLOCKED",
                "run_error": sanitize(requested.stderr or requested.stdout),
            }
        )
        write_evidence(evidence_file, payload)
        return payload

    payload.update(
        {
            "ok": True,
            "result": "EXISTING_DESKTOP_WATCHDOG_RUN_REQUESTED",
            "run_requested": True,
        }
    )
    write_evidence(evidence_file, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--allow-uac", action="store_true")
    parser.add_argument("--uac-confirm", default="")
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("artifacts/noteri-desktop-watchdog-recovery/evidence.json"),
    )
    args = parser.parse_args()
    try:
        result = recover(
            confirm=args.confirm,
            evidence_file=args.evidence_file.resolve(),
            repair=lambda: repair_watchdog_task(
                args.source_sha,
                allow_uac=args.allow_uac,
                uac_confirm=args.uac_confirm,
            ),
        )
    except (RecoveryError, OSError, subprocess.SubprocessError) as exc:
        blocked = {
            "schema_version": "1",
            "generated_at_utc": now_iso(),
            "ok": False,
            "result": "NOTERI_DESKTOP_WATCHDOG_RECOVERY_BLOCKED",
            "error": sanitize(exc),
            "production_touched": False,
            "secrets_read": False,
            "credentials_supplied": False,
            "task_created_or_modified": False,
        }
        write_evidence(args.evidence_file.resolve(), blocked)
        print(json.dumps(blocked, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
