#!/usr/bin/env python3
"""Inventário SQL/Docker local e somente leitura para o canário físico do Desktop."""
from __future__ import annotations

import ctypes
import hashlib
import json
import ntpath
import os
import re
import shutil
import subprocess
from collections.abc import Callable

LOCAL_ENGINES = (
    ("desktop-linux", "npipe:////./pipe/dockerDesktopLinuxEngine"),
    ("default-local", "npipe:////./pipe/docker_engine"),
)
FIXED_SERVICES = (
    "MSSQLSERVER",
    "SQLSERVERAGENT",
    "SQLBrowser",
    "SQLWriter",
    "com.docker.service",
    "docker",
)
SERVICE_STATES = {
    1: "stopped",
    2: "start_pending",
    3: "stop_pending",
    4: "running",
    5: "continue_pending",
    6: "pause_pending",
    7: "paused",
}
CONTAINER_STATES = {
    "created", "restarting", "running", "removing", "paused", "exited", "dead",
}
MAX_RECORDS = 64
MAX_OUTPUT_BYTES = 512 * 1024
DockerRunner = Callable[[list[str], dict[str, str]], str]


class InventoryError(RuntimeError):
    """Only static non-sensitive reason codes may cross this boundary."""


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _docker_env() -> dict[str, str]:
    # Explicit local npipe endpoints only. Never read an existing Docker context
    # or authentication config, and never accept DOCKER_HOST from an agent.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("DOCKER_")}
    env["DOCKER_CONFIG"] = ntpath.join(
        env.get("RUNNER_TEMP", r"C:\Windows\Temp"), "_reqsys_sql_readonly_docker_config_absent"
    )
    return env


def _default_docker_runner(args: list[str], env: dict[str, str]) -> str:
    try:
        result = subprocess.run(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", timeout=8, check=False, shell=False, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        raise InventoryError("docker_command_unavailable") from None
    if result.returncode != 0 or len(result.stdout.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise InventoryError("docker_command_unavailable")
    return result.stdout


def _docker_read(
    cli: str, endpoint: str, subcommand: list[str], runner: DockerRunner
) -> str:
    # Every Docker verb/argument is constant at its call site. No shell or
    # user-configured remote daemon, registry pull or inspect.
    return runner([cli, "--host", endpoint, *subcommand], _docker_env())


def _json_lines(raw: str) -> list[dict]:
    lines = raw.splitlines()
    if len(lines) > MAX_RECORDS:
        raise InventoryError("docker_list_limit")
    result = []
    for line in lines:
        if line.strip():
            try:
                record = json.loads(line)
            except (ValueError, TypeError):
                raise InventoryError("docker_metadata_invalid") from None
            if not isinstance(record, dict):
                raise InventoryError("docker_metadata_invalid")
            result.append(record)
    return result


def _published_tcp_ports(value: object) -> list[int]:
    if not isinstance(value, str):
        return []
    ports = {
        int(match)
        for match in re.findall(r"(?<!\d)(\d{1,5})->\d{1,5}/tcp\b", value)
        if 1 <= int(match) <= 65535
    }
    return sorted(ports)


def _docker_summary(*, cli_path: str | None, runner: DockerRunner) -> dict:
    result = {
        "cli_present": bool(cli_path),
        "engine_verified": False,
        "engine_type": None,
        "engine_version": None,
        "local_endpoint": None,
        "containers": [],
        "volumes": [],
        "networks": [],
        "published_tcp_ports": [],
        "reason": None,
        "status": "unavailable",
    }
    if not cli_path:
        result["reason"] = "docker_cli_missing"
        return result
    normalized = ntpath.normcase(ntpath.normpath(cli_path))
    trusted_prefixes = (
        "c:\\program files\\docker\\docker\\resources\\bin\\",
        "c:\\programdata\\dockerdesktop\\version-bin\\",
    )
    if (
        ntpath.basename(normalized) != "docker.exe"
        or not ntpath.isabs(normalized)
        or not any(normalized.startswith(prefix) for prefix in trusted_prefixes)
    ):
        result["reason"] = "docker_cli_untrusted"
        return result
    version: dict | None = None
    endpoint: str | None = None
    endpoint_kind: str | None = None
    for kind, candidate in LOCAL_ENGINES:
        try:
            raw = _docker_read(cli_path, candidate, ["version", "--format", "{{json .Server}}"], runner)
            candidate_version = json.loads(raw)
            if (
                isinstance(candidate_version, dict)
                and candidate_version.get("Os") in {"linux", "windows"}
                and re.fullmatch(r"\d+\.\d+(?:\.\d+)?[a-zA-Z0-9.+-]*",
                                 str(candidate_version.get("Version", "")))
            ):
                version = candidate_version
                endpoint = candidate
                endpoint_kind = kind
                break
        except (InventoryError, ValueError, TypeError):
            continue
    if version is None or endpoint is None:
        result["reason"] = "local_engine_not_verified"
        return result
    result.update({
        "engine_verified": True,
        "engine_type": version["Os"],
        "engine_version": version["Version"][:48],
        "local_endpoint": endpoint_kind,
    })
    fixed_commands = {
        "containers": ["ps", "--all", "--format", "{{json .}}"],
        "volumes": ["volume", "ls", "--format", "{{json .}}"],
        "networks": ["network", "ls", "--format", "{{json .}}"],
    }
    try:
        raw_lists = {
            name: _json_lines(_docker_read(cli_path, endpoint, args, runner))
            for name, args in fixed_commands.items()
        }
        ports = set()
        for item in raw_lists["containers"]:
            state = str(item.get("State", "")).lower()
            published = _published_tcp_ports(item.get("Ports"))
            ports.update(published)
            result["containers"].append({
                "name_hash": fingerprint(str(item.get("Names", ""))),
                "state": state if state in CONTAINER_STATES else "unknown",
                "sqlserver_image": "mcr.microsoft.com/mssql/server" in
                    str(item.get("Image", "")).lower(),
                "published_tcp_ports": published,
            })
        for item in raw_lists["volumes"]:
            driver = str(item.get("Driver", "")).lower()
            result["volumes"].append({
                "name_hash": fingerprint(str(item.get("Name", ""))),
                "driver": driver if driver in {"local", "nfs"} else "other",
            })
        for item in raw_lists["networks"]:
            driver = str(item.get("Driver", "")).lower()
            flag = str(item.get("Internal", "")).lower()
            result["networks"].append({
                "name_hash": fingerprint(str(item.get("Name", ""))),
                "driver": driver if driver in {"bridge", "host", "none", "overlay", "nat"} else "other",
                "internal": True if flag == "true" else False if flag == "false" else None,
            })
    except InventoryError as error:
        result["status"] = "partial"
        result["reason"] = str(error)
        return result
    result["published_tcp_ports"] = sorted(ports)
    result["status"] = "measured"
    return result


def _service_names() -> list[str]:
    import winreg

    names = set(FIXED_SERVICES)
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services"
        ) as root:
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(root, index)
                except OSError as error:
                    if getattr(error, "winerror", None) != 259:
                        raise InventoryError("service_registry_unavailable") from None
                    break
                if re.fullmatch(r"(?:MSSQL|SQLAgent)\$[A-Za-z0-9_-]{1,80}", name, re.I):
                    names.add(name)
                index += 1
    except OSError:
        raise InventoryError("service_registry_unavailable") from None
    if len(names) > MAX_RECORDS:
        raise InventoryError("service_inventory_limit")
    return sorted(names)


def _windows_services() -> dict:
    """SCM QueryServiceStatusEx, no PowerShell/sc.exe/WMI/terminal."""
    from ctypes import wintypes

    class ServiceStatus(ctypes.Structure):
        _fields_ = [(name, wintypes.DWORD) for name in (
            "service_type", "current_state", "controls_accepted",
            "win32_exit_code", "service_specific_exit_code",
            "check_point", "wait_hint", "process_id", "service_flags",
        )]

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    advapi.OpenSCManagerW.restype = wintypes.HANDLE
    advapi.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    advapi.OpenServiceW.restype = wintypes.HANDLE
    advapi.QueryServiceStatusEx.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    advapi.QueryServiceStatusEx.restype = wintypes.BOOL
    advapi.CloseServiceHandle.argtypes = [wintypes.HANDLE]
    advapi.CloseServiceHandle.restype = wintypes.BOOL
    scm = advapi.OpenSCManagerW(None, None, 1)
    if not scm:
        raise InventoryError("scm_read_unavailable")
    results = []
    try:
        for name in _service_names():
            service = advapi.OpenServiceW(scm, name, 4)
            if not service:
                if ctypes.get_last_error() != 1060:  # ERROR_SERVICE_DOES_NOT_EXIST
                    raise InventoryError("scm_service_read_unavailable")
                continue
            try:
                status = ServiceStatus()
                needed = wintypes.DWORD()
                ok = advapi.QueryServiceStatusEx(
                    service, 0, ctypes.byref(status), ctypes.sizeof(status), ctypes.byref(needed)
                )
                if not ok:
                    raise InventoryError("scm_service_read_unavailable")
                kind = (
                    "sql_engine" if name.upper().startswith("MSSQL")
                    else "sql_agent" if name.upper().startswith("SQLAGENT")
                    or name.upper() == "SQLSERVERAGENT"
                    else "sql_auxiliary" if name.upper().startswith(("SQLBROWSER", "SQLWRITER"))
                    else "docker"
                )
                results.append({
                    "name_hash": fingerprint(name),
                    "kind": kind,
                    "state": SERVICE_STATES.get(status.current_state, "unknown"),
                })
            finally:
                advapi.CloseServiceHandle(service)
    finally:
        advapi.CloseServiceHandle(scm)
    return {
        "status": "measured", "services": results,
        "sql_engine_running": sum(
            x["kind"] == "sql_engine" and x["state"] == "running" for x in results
        ),
    }


def collect(
    *,
    platform: str | None = None,
    cli_path: str | None = None,
    docker_runner: DockerRunner | None = None,
    service_reader: Callable[[], dict] | None = None,
) -> dict:
    """Never permits HML provisioning. Fail closed and suppress raw exceptions."""
    result = {
        "schema_version": "1",
        "status": "unavailable",
        "reason": None,
        "docker": {"status": "unavailable", "engine_verified": False},
        "windows_services": {"status": "unavailable"},
        "hml_provisioning_authorized": False,
        "production_touched": False,
        "secrets_read": False,
    }
    if (platform or os.name) != "nt":
        result["reason"] = "windows_required"
        return result
    try:
        result["docker"] = _docker_summary(
            cli_path=cli_path if cli_path is not None else shutil.which("docker.exe"),
            runner=docker_runner or _default_docker_runner,
        )
    except Exception:
        result["docker"] = {
            "status": "unavailable", "engine_verified": False,
            "reason": "docker_probe_failed",
        }
    try:
        services = (service_reader or _windows_services)()
        if not isinstance(services, dict) or services.get("status") != "measured":
            raise InventoryError("service_proof_invalid")
        result["windows_services"] = services
    except Exception:
        result["windows_services"] = {
            "status": "unavailable", "reason": "service_probe_failed"
        }
    docker_status = result["docker"].get("status")
    services_status = result["windows_services"].get("status")
    if docker_status == "measured" and services_status == "measured":
        result["status"] = "measured"
    elif docker_status != "unavailable" or services_status == "measured":
        result["status"] = "partial"
        result["reason"] = "incomplete_runtime_inventory"
    else:
        result["reason"] = "runtime_inventory_unavailable"
    return result
