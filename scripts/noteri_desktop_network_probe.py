#!/usr/bin/env python3
"""Sonda governada e somente leitura do Noteri para o Desktop PC24x7."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
CONFIRM = "PROBE-NOTERI-DESKTOP-NETWORK"
RUNTIME_PORT = 8081
PING_TIMEOUT_MS = 1500
TCP_TIMEOUT_SECONDS = 1.5
ADMIN_STAGING_PATH = "\\\\" + TARGET_HOST + "\\C$\\Users\\Public\\Desktop"
WMI_NAMESPACE = r"root\cimv2"
WMI_QUERY_CLASS = "Win32_OperatingSystem"
WMI_QUERY = f"SELECT Caption FROM {WMI_QUERY_CLASS}"


class ProbeError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_host() -> str:
    if os.name != "nt":
        raise ProbeError("Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise ProbeError(f"host não autorizado: {host}")
    return host


def validate_request(confirm: str, correlation_id: str) -> str:
    if confirm != CONFIRM:
        raise ProbeError("confirmação inválida")
    value = correlation_id.strip()
    if not 8 <= len(value) <= 160:
        raise ProbeError("correlation_id inválido")
    return value


def resolve_target() -> dict[str, Any]:
    try:
        info = socket.getaddrinfo(
            TARGET_HOST,
            RUNTIME_PORT,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        return {"resolved": False, "address_count": 0}

    addresses = {
        str(item[4][0])
        for item in info
        if len(item) >= 5 and item[4] and item[4][0]
    }
    return {
        "resolved": bool(addresses),
        "address_count": len(addresses),
    }


def ping_path() -> Path:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    target = root / "System32" / "PING.EXE"
    if not target.is_file():
        raise ProbeError("PING.EXE não encontrado")
    return target


def icmp_reachable() -> bool:
    completed = subprocess.run(
        [
            str(ping_path()),
            "-n",
            "1",
            "-w",
            str(PING_TIMEOUT_MS),
            TARGET_HOST,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    )
    return completed.returncode == 0


def runtime_port_reachable() -> bool:
    try:
        with socket.create_connection(
            (TARGET_HOST, RUNTIME_PORT),
            timeout=TCP_TIMEOUT_SECONDS,
        ):
            return True
    except OSError:
        return False


def admin_staging_path_probe() -> dict[str, Any]:
    """Comprova somente acesso de leitura via C$; não grava nem persiste listagem."""
    try:
        with os.scandir(ADMIN_STAGING_PATH) as entries:
            next(entries, None)
        return {"reachable": True, "result": "accessible"}
    except PermissionError:
        return {"reachable": False, "result": "access_denied"}
    except FileNotFoundError:
        return {"reachable": False, "result": "not_found"}
    except OSError as exc:
        code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
        return {
            "reachable": False,
            "result": f"os_error_{code}" if code is not None else "os_error",
        }


def _wmi_client():
    pythoncom = importlib.import_module("pythoncom")
    win32com_client = importlib.import_module("win32com.client")
    return pythoncom, win32com_client


def _classify_wmi_error(exc: BaseException) -> str:
    codes: list[int] = []
    for attr in ("hresult", "winerror", "errno"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            codes.append(value)
    for value in getattr(exc, "args", ()):
        if isinstance(value, int):
            codes.append(value)

    unsigned = {value & 0xFFFFFFFF for value in codes}
    if 0x80070005 in unsigned or 5 in codes:
        return "access_denied"
    if 0x800706BA in unsigned:
        return "rpc_server_unavailable"
    if 0x8004100E in unsigned:
        return "namespace_unavailable"
    return "wmi_error"


def wmi_readonly_probe() -> dict[str, Any]:
    """Consulta WMI por DCOM usando a identidade corrente, sem credenciais ou mutação."""
    try:
        pythoncom, win32com_client = _wmi_client()
    except ImportError:
        return {
            "reachable": False,
            "result": "dependency_unavailable",
            "namespace": WMI_NAMESPACE,
            "query_class": WMI_QUERY_CLASS,
        }

    initialized = False
    try:
        pythoncom.CoInitialize()
        initialized = True
        locator = win32com_client.Dispatch("WbemScripting.SWbemLocator")
        services = locator.ConnectServer(TARGET_HOST, WMI_NAMESPACE)
        services.Security_.ImpersonationLevel = 3
        rows = services.ExecQuery(WMI_QUERY, "WQL", 0x20)
        count = 0
        for _ in rows:
            count += 1
            if count >= 2:
                break
        return {
            "reachable": count > 0,
            "result": "accessible" if count > 0 else "empty_result",
            "namespace": WMI_NAMESPACE,
            "query_class": WMI_QUERY_CLASS,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "result": _classify_wmi_error(exc),
            "namespace": WMI_NAMESPACE,
            "query_class": WMI_QUERY_CLASS,
        }
    finally:
        if initialized:
            pythoncom.CoUninitialize()


def probe(confirm: str, correlation_id: str) -> dict[str, Any]:
    correlation_id = validate_request(confirm, correlation_id)
    host = validate_host()
    resolution = resolve_target()

    icmp: bool | None = None
    tcp = False
    staging = {"reachable": False, "result": "not_attempted"}
    wmi = {
        "reachable": False,
        "result": "not_attempted",
        "namespace": WMI_NAMESPACE,
        "query_class": WMI_QUERY_CLASS,
    }
    if resolution["resolved"]:
        icmp = icmp_reachable()
        tcp = runtime_port_reachable()
        staging = admin_staging_path_probe()
        wmi = wmi_readonly_probe()

    if not resolution["resolved"]:
        state = "name_resolution_failed"
        desktop_reachable = False
    elif tcp:
        state = "runtime_port_reachable"
        desktop_reachable = True
    elif icmp:
        state = "host_reachable_runtime_port_closed"
        desktop_reachable = True
    elif wmi["reachable"]:
        state = "host_reachable_wmi_runtime_port_closed"
        desktop_reachable = True
    else:
        state = "resolved_not_reachable"
        desktop_reachable = False

    return {
        "ok": True,
        "probe_completed": True,
        "source_host": host,
        "target_host": TARGET_HOST,
        "dns_resolved": resolution["resolved"],
        "resolved_address_count": resolution["address_count"],
        "icmp_reachable": icmp,
        "runtime_port": RUNTIME_PORT,
        "runtime_port_reachable": tcp,
        "admin_staging_path_reachable": bool(staging["reachable"]),
        "admin_staging_path_result": staging["result"],
        "admin_staging_path": r"C:\Users\Public\Desktop",
        "wmi_reachable": bool(wmi["reachable"]),
        "wmi_result": str(wmi["result"]),
        "wmi_namespace": str(wmi["namespace"]),
        "wmi_query_class": str(wmi["query_class"]),
        "wmi_read_only": True,
        "desktop_reachable": desktop_reachable,
        "network_state": state,
        "correlation_id": correlation_id,
        "rdc_required": False,
        "remote_shell_used": False,
        "credentials_supplied": False,
        "production_touched": False,
        "secrets_read": False,
        "observed_at": now_iso(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    code = 0
    try:
        payload = probe(args.confirm, args.correlation_id)
    except (ProbeError, OSError, subprocess.SubprocessError) as exc:
        payload = {
            "ok": False,
            "probe_completed": False,
            "source_host": socket.gethostname(),
            "target_host": TARGET_HOST,
            "correlation_id": args.correlation_id,
            "error": str(exc)[:1000],
            "error_type": type(exc).__name__,
            "rdc_required": False,
            "remote_shell_used": False,
            "credentials_supplied": False,
            "production_touched": False,
            "secrets_read": False,
            "observed_at": now_iso(),
        }
        code = 2

    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
