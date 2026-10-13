#!/usr/bin/env python3
"""Canário mínimo e sanitizado de pickup físico do runner DESKTOP-PDQK954."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import socket
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

TARGET_HOST = "DESKTOP-PDQK954"
CONFIRM = "PROVE-DESKTOP-GITHUB-RUNNER-PICKUP"


class CanaryError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_evidence(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )



class MemoryStatus(ctypes.Structure):
    """Windows MEMORYSTATUSEX, stable Win32 ABI (no shell/process calls)."""

    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def windows_memory_bytes() -> tuple[int, int]:
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise CanaryError("capacity_memory_unavailable")
    return int(status.ullTotalPhys), int(status.ullAvailPhys)


def sql_instance_registry_count() -> int | None:
    """Count registered SQL Server instances, not proof of running services."""
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL",
        ) as key:
            count = 0
            while True:
                try:
                    winreg.EnumValue(key, count)
                except OSError:
                    break
                count += 1
            return count
    except FileNotFoundError:
        return 0
    except OSError:
        # Registry access uncertainty cannot mean 'no SQL Server'.
        return None


def host_capacity(
    *,
    memory_reader: Callable[[], tuple[int, int]] | None = None,
    disk_reader: Callable[[str], object] | None = None,
    cpu_reader: Callable[[], int | None] | None = None,
    sql_reader: Callable[[], int | None] | None = None,
    docker_reader: Callable[[], bool] | None = None,
    system_drive: str | None = None,
) -> dict:
    """Non-mutating capacity snapshot; never infer HML readiness from one metric."""
    drive = system_drive if system_drive is not None else os.environ.get("SystemDrive", "C:")
    if not re.fullmatch(r"[A-Za-z]:", drive):
        raise CanaryError("capacity_drive_invalid")
    memory_total, memory_available = (memory_reader or windows_memory_bytes)()
    disk = (disk_reader or shutil.disk_usage)(drive + "\\")
    cpu_logical = (cpu_reader or os.cpu_count)()
    sql_count = (sql_reader or sql_instance_registry_count)()
    docker_present = (docker_reader or (lambda: shutil.which("docker") is not None))()

    if (
        not isinstance(cpu_logical, int)
        or cpu_logical <= 0
        or memory_total <= 0
        or memory_available < 0
        or memory_available > memory_total
        or disk.total <= 0
        or disk.free < 0
        or disk.free > disk.total
        or (sql_count is not None and (not isinstance(sql_count, int) or sql_count < 0))
    ):
        raise CanaryError("capacity_metrics_invalid")

    gib = 1024**3
    return {
        "status": "measured",
        "logical_cpu_count": cpu_logical,
        "ram_total_gib": round(memory_total / gib, 2),
        "ram_available_gib": round(memory_available / gib, 2),
        "system_drive": drive.upper(),
        "system_disk_total_gib": round(disk.total / gib, 2),
        "system_disk_free_gib": round(disk.free / gib, 2),
        "registered_sql_instances": sql_count,
        "registered_sql_instances_are_live": False,
        "docker_cli_present": bool(docker_present),
        "docker_daemon_verified": False,
        "hml_existing_verified": False,
        "hml_provisioning_authorized": False,
        "production_touched": False,
        "secrets_read": False,
    }


def execute(
    *,
    confirm: str,
    evidence_file: Path,
    host: str | None = None,
    platform: str | None = None,
    capacity_probe: Callable[[], dict] | None = None,
    runtime_probe: Callable[[], dict] | None = None,
) -> dict:
    if confirm != CONFIRM:
        raise CanaryError("confirmation_invalid")
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    if actual_platform != "nt":
        raise CanaryError("windows_required")
    if actual_host.casefold() != TARGET_HOST.casefold():
        raise CanaryError(f"wrong_host:{actual_host}")
    runner_name = os.environ.get("RUNNER_NAME", "")
    if runner_name.casefold() != TARGET_HOST.casefold():
        raise CanaryError(f"runner_name_mismatch:{runner_name}")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    if repository != "ericson-j-santos/reqsys-v2-enterprise-real":
        raise CanaryError("repository_mismatch")
    if len(sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
        raise CanaryError("github_sha_invalid")

    evidence = {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "ok": True,
        "result": "DESKTOP_GITHUB_RUNNER_PICKUP_PROVEN",
        "host": actual_host,
        "runner_name": runner_name,
        "repository": repository,
        "sha": sha.lower(),
        "production_touched": False,
        "secrets_read": False,
    }
    # Capacity is independent of runner pickup: never turn a failed inventory
    # into a false HML ready signal, and never disclose exception contents.
    try:
        snapshot = (capacity_probe or host_capacity)()
        if not isinstance(snapshot, dict) or snapshot.get("status") != "measured":
            raise CanaryError("capacity_proof_invalid")
        evidence["capacity"] = snapshot
    except Exception:
        evidence["capacity"] = {
            "status": "unavailable",
            "reason": "capacity_probe_failed",
            "hml_provisioning_authorized": False,
        }
    # Independent, strictly read-only runtime inspection. An offline Docker
    # engine must never cause a false-positive HML authorization.
    try:
        if runtime_probe is None:
            from desktop_sql_hml_host_inventory_dev import collect as runtime_probe
        runtime = runtime_probe()
        if (
            not isinstance(runtime, dict)
            or runtime.get("status") not in {"measured", "partial", "unavailable"}
            or runtime.get("hml_provisioning_authorized") is not False
            or runtime.get("production_touched") is not False
            or runtime.get("secrets_read") is not False
        ):
            raise CanaryError("runtime_proof_invalid")
        evidence["sql_hml_host_inventory"] = runtime
    except Exception:
        evidence["sql_hml_host_inventory"] = {
            "status": "unavailable",
            "reason": "runtime_probe_failed",
            "hml_provisioning_authorized": False,
            "production_touched": False,
            "secrets_read": False,
        }
    write_evidence(evidence_file, evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("artifacts/desktop-runner-pickup/evidence.json"),
    )
    args = parser.parse_args()
    try:
        result = execute(confirm=args.confirm, evidence_file=args.evidence_file.resolve())
    except (CanaryError, OSError):
        blocked = {
            "schema_version": "1",
            "generated_at_utc": now_iso(),
            "ok": False,
            "result": "DESKTOP_GITHUB_RUNNER_PICKUP_NOT_PROVEN",
            "error": "desktop_runner_pickup_not_proven",
            "production_touched": False,
            "secrets_read": False,
        }
        write_evidence(args.evidence_file.resolve(), blocked)
        print(json.dumps(blocked, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
