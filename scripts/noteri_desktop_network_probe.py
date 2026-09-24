#!/usr/bin/env python3
"""Sonda de rede fail-closed do Noteri para o Desktop PC24x7."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
CONFIRM = "PROBE-NOTERI-DESKTOP-NETWORK"
RUNTIME_PORT = 8081
ORCHESTRATOR_BASE = "http://DESKTOP-PDQK954:8787"
RUNNER_RECOVERY_TASK = "host.github_runner.recover.v1"
CONTROL_PORTS = {
    "ssh": 22,
    "rpc_epmapper": 135,
    "smb": 445,
    "winrm_http": 5985,
    "winrm_https": 5986,
    "rdp": 3389,
    "engineering_orchestrator": 8787,
}
PING_TIMEOUT_MS = 1500
TCP_TIMEOUT_SECONDS = 1.5
ADMIN_STAGING_PATH = "\\\\" + TARGET_HOST + "\\C$\\Users\\Public\\Desktop"


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
    root = Path(os.environ.get("SystemRoot") or r"C:\\Windows")
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


def tcp_port_reachable(port: int) -> bool:
    try:
        with socket.create_connection(
            (TARGET_HOST, port),
            timeout=TCP_TIMEOUT_SECONDS,
        ):
            return True
    except OSError:
        return False


def runtime_port_reachable() -> bool:
    return tcp_port_reachable(RUNTIME_PORT)


def control_port_reachability() -> dict[str, bool]:
    return {
        name: tcp_port_reachable(port)
        for name, port in CONTROL_PORTS.items()
    }


def orchestrator_readback() -> dict[str, Any]:
    def get_json(path: str) -> tuple[int | None, Any]:
        request = urllib.request.Request(
            ORCHESTRATOR_BASE + path,
            headers={"Accept": "application/json", "Cache-Control": "no-store"},
        )
        try:
            with urllib.request.urlopen(request, timeout=3.0) as response:
                status = int(response.status)
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return int(exc.code), None
        except (urllib.error.URLError, OSError):
            return None, None
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError:
            return status, None

    ready_status, ready_payload = get_json("/readyz")
    workers_status, workers_payload = get_json("/v1/workers")
    workers = workers_payload.get("workers") if isinstance(workers_payload, dict) else None
    matches = []
    if isinstance(workers, list):
        matches = [
            item for item in workers
            if isinstance(item, dict)
            and str(item.get("device_name") or "").casefold() == TARGET_HOST.casefold()
        ]

    desktop = None
    if len(matches) == 1:
        worker = matches[0]
        capabilities = worker.get("capabilities") if isinstance(worker.get("capabilities"), dict) else {}
        safe_types = capabilities.get("safe_task_types")
        if not isinstance(safe_types, list):
            safe_types = []
        desktop = {
            "fresh": worker.get("fresh") is True,
            "controller_online": worker.get("controller_online") is True,
            "auth_valid": worker.get("auth_valid") is True,
            "eligible": worker.get("eligible") is True,
            "profile": str(worker.get("profile") or "").strip().upper(),
            "runner_recovery_capable": RUNNER_RECOVERY_TASK in safe_types,
            "rdc_recovery_capable": "host.rdc.recover.v1" in safe_types,
            "orchestrator_refresh_capable": "host.orchestrator.refresh.v1" in safe_types,
        }

    return {
        "ready_http_status": ready_status,
        "ready": (
            ready_status == 200
            and isinstance(ready_payload, dict)
            and ready_payload.get("ready") is True
        ),
        "workers_http_status": workers_status,
        "worker_match_count": len(matches) if isinstance(workers, list) else None,
        "desktop_worker": desktop,
    }


def admin_staging_path_probe() -> dict[str, Any]:
    """Comprova apenas acesso de leitura ao Desktop Público via C$; não grava nada."""
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


def probe(confirm: str, correlation_id: str) -> dict[str, Any]:
    correlation_id = validate_request(confirm, correlation_id)
    host = validate_host()
    resolution = resolve_target()

    icmp: bool | None = None
    tcp = False
    staging = {"reachable": False, "result": "not_attempted"}
    control_ports = {name: False for name in CONTROL_PORTS}
    orchestrator = {
        "ready_http_status": None,
        "ready": False,
        "workers_http_status": None,
        "worker_match_count": None,
        "desktop_worker": None,
    }
    if resolution["resolved"]:
        icmp = icmp_reachable()
        tcp = runtime_port_reachable()
        control_ports = control_port_reachability()
        if control_ports.get("engineering_orchestrator") is True:
            orchestrator = orchestrator_readback()
        staging = admin_staging_path_probe()

    if not resolution["resolved"]:
        state = "name_resolution_failed"
        desktop_reachable = False
    elif tcp:
        state = "runtime_port_reachable"
        desktop_reachable = True
    elif icmp:
        state = "host_reachable_runtime_port_closed"
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
        "control_ports": control_ports,
        "engineering_orchestrator": orchestrator,
        "admin_staging_path_reachable": bool(staging["reachable"]),
        "admin_staging_path_result": staging["result"],
        "admin_staging_path": r"C:\Users\Public\Desktop",
        "desktop_reachable": desktop_reachable,
        "network_state": state,
        "correlation_id": correlation_id,
        "rdc_required": False,
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
