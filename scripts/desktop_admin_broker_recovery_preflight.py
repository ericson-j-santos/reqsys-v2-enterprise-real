#!/usr/bin/env python3
"""Somente diagnostica se o reparo nativo fixo do Desktop pode ser executado.

Sem mutações, sem elevação/UAC, sem token em logs e sem comando arbitrário.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import locale
import os
import re
import shutil
import socket
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

HOST = "DESKTOP-PDQK954"
CONFIRM = "PROBE-DESKTOP-ADMIN-BROKER-REPAIR"
TASKS = {
    "broker": (r"\Automation\ReqSysDesktopAdminBroker", "DesktopAdminBroker", "HighestAvailable"),
    "watchdog": (r"\Automation\ReqSysDesktopControlPlaneWatchdog", "DesktopControlPlaneWatchdog", "LeastPrivilege"),
}
HEX_SHA = re.compile(r"^[a-f0-9]{40}$")


def path_equal(left: object, right: object) -> bool:
    """Compara caminhos sem executar o conteúdo de metadata não confiável."""
    if not isinstance(left, str) or not left:
        return False
    try:
        a = os.path.normcase(str(Path(left).resolve(strict=False)))
        b = os.path.normcase(str(Path(right).resolve(strict=False)))
    except (OSError, ValueError, TypeError):
        return False
    return a == b


def installed_runtime(base: Path, leaf: str) -> dict:
    root = base / "ReqSys" / leaf
    metadata_path = root / "metadata.json"
    outcome: dict = {"valid": False, "source_sha": None}
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        if not isinstance(metadata, dict) or str(metadata.get("host", "")).casefold() != HOST.casefold():
            return outcome
        sha = str(metadata.get("source_sha") or "").lower()
        if not HEX_SHA.fullmatch(sha):
            return outcome
        release = root / "releases" / sha
        launcher = root / "run.py"
        python_raw = metadata.get("python_executable")
        if not path_equal(metadata.get("runtime_root"), str(root)):
            return outcome
        if not path_equal(metadata.get("release_root"), str(release)):
            return outcome
        if not isinstance(python_raw, str) or not Path(python_raw).is_file():
            return outcome
        if not release.is_dir() or not launcher.is_file():
            return outcome
        return {
            "valid": True, "source_sha": sha, "python": python_raw,
            "launcher": str(launcher), "root": str(root),
        }
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return outcome


def task_contract_checks(xml: str | None, runtime: dict, runlevel: str) -> dict[str, bool]:
    """Diagnostica o contrato sem serializar XML, caminhos ou identidade."""
    checks = {
        "xml_valid": False,
        "runtime_valid": bool(runtime.get("valid")),
        "boot_trigger": False,
        "logon_s4u": False,
        "runlevel_expected": False,
        "command_matches": False,
        "arguments_match": False,
        "working_dir_matches": False,
    }
    if xml is None:
        return checks
    try:
        tree = ET.fromstring(xml)
        checks["xml_valid"] = True
        checks["boot_trigger"] = tree.find(".//{*}BootTrigger") is not None
        checks["logon_s4u"] = tree.findtext(".//{*}Principal/{*}LogonType") == "S4U"
        checks["runlevel_expected"] = tree.findtext(".//{*}Principal/{*}RunLevel") == runlevel
        command = tree.findtext(".//{*}Actions/{*}Exec/{*}Command")
        arguments = tree.findtext(".//{*}Actions/{*}Exec/{*}Arguments")
        working = tree.findtext(".//{*}Actions/{*}Exec/{*}WorkingDirectory")
        if checks["runtime_valid"]:
            checks["command_matches"] = bool(command) and path_equal(command.strip('"'), runtime.get("python"))
            checks["arguments_match"] = bool(arguments) and path_equal(arguments.strip().strip('"'), runtime.get("launcher"))
            checks["working_dir_matches"] = bool(working) and path_equal(working.strip('"'), runtime.get("root"))
    except (ET.ParseError, OSError, ValueError, TypeError):
        pass
    return checks


def task_contract(xml: str | None, runtime: dict, runlevel: str) -> bool:
    """Valida tarefa existente: boot, S4U, nível e ação exata fixada."""
    return all(task_contract_checks(xml, runtime, runlevel).values())


def query_task_xml(task_name: str) -> str | None:
    """Somente schtasks /Query: nunca /Run, /Create ou /Change."""
    try:
        process = subprocess.run(
            ["schtasks.exe", "/Query", "/TN", task_name, "/XML"],
            capture_output=True, text=True, check=False, timeout=15,
            encoding=locale.getpreferredencoding(False) or "utf-8", errors="replace",
        )
        return process.stdout if process.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def elevated_token() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError, ValueError):
        return False


def local_gh_auth() -> bool:
    gh = shutil.which("gh")
    if not gh:
        return False
    env = {key: value for key, value in os.environ.items()
           if key.upper() not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")}
    try:
        result = subprocess.run(
            [gh, "auth", "status", "--hostname", "github.com"],
            env=env, capture_output=True, text=True, timeout=15, check=False,
        )
        # stdout/stderr podem conter informações da conta: nunca serializar.
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def inspect(
    *, base: Path, host: str, platform: str, elevated: bool,
    gh_authenticated: bool, query_xml: Callable[[str], str | None],
) -> dict:
    if host.casefold() != HOST.casefold() or platform != "nt":
        return {"schema_version": "1", "preflight_completed": False,
                "status": "BLOCKED_WRONG_HOST_OR_PLATFORM", "host_expected": HOST}
    runtimes = {key: installed_runtime(base, spec[1]) for key, spec in TASKS.items()}
    task_checks = {
        key: task_contract_checks(query_xml(spec[0]), runtimes[key], spec[2])
        for key, spec in TASKS.items()
    }
    tasks = {key: all(checks.values()) for key, checks in task_checks.items()}
    runtime_ok = all(v["valid"] for v in runtimes.values())
    task_ok = all(tasks.values())
    if not runtime_ok:
        status = "BLOCKED_PERSISTENT_RUNTIME_INVALID"
    elif not task_ok and not elevated:
        status = "BLOCKED_ADMIN_ELEVATION_REQUIRED"
    elif not task_ok:
        status = "NATIVE_REPAIR_ELIGIBLE_NOT_EXECUTED"
    elif not gh_authenticated:
        status = "BLOCKED_GH_LOCAL_AUTH_UNAVAILABLE"
    else:
        status = "EXISTING_TASKS_AND_AUTH_READY"
    return {
        "schema_version": "1", "preflight_completed": True,
        "host_expected": HOST, "environment": "local/DEV",
        "status": status, "runner_is_elevated": bool(elevated),
        "gh_local_auth_available": bool(gh_authenticated),
        "task_contract": tasks,
        "task_contract_checks": task_checks,
        "runtime_contract": {k: v["valid"] for k, v in runtimes.items()},
        "runtime_source_sha": {k: v["source_sha"] for k, v in runtimes.items()},
        "repaired": False, "task_created_or_modified": False,
        "production_touched": False, "secrets_logged": False,
        "reboot_performed": False, "rdc_required": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.confirm != CONFIRM:
        print(json.dumps({"status": "BLOCKED_CONFIRMATION_INVALID", "preflight_completed": False}))
        return 2
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        print(json.dumps({"status": "BLOCKED_LOCALAPPDATA_MISSING", "preflight_completed": False}))
        return 2
    evidence = inspect(
        base=Path(base), host=socket.gethostname(), platform=os.name,
        elevated=elevated_token(), gh_authenticated=local_gh_auth(),
        query_xml=query_task_xml,
    )
    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence["status"] in (
        "NATIVE_REPAIR_ELIGIBLE_NOT_EXECUTED", "EXISTING_TASKS_AND_AUTH_READY"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())

