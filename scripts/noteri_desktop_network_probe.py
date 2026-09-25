#!/usr/bin/env python3
"""Sonda governada e somente leitura de superfícies runtime Noteri -> Desktop."""

from __future__ import annotations

import argparse
import json
import os
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
CONFIRM = "PROBE-NOTERI-DESKTOP-NETWORK"
PROBE_REVISION = "runtime-surfaces-v1"
TCP_TIMEOUT_SECONDS = 1.5
HTTP_TIMEOUT_SECONDS = 3.0

SURFACES = {
    "reqsys_dev_gateway": {"port": 8083, "path": "/api/health"},
    "codex_backend": {"port": 8000, "path": "/health"},
    "codex_gateway": {"port": 8008, "path": "/health"},
    "engineering_worker_pool": {"port": 8097, "path": "/health"},
    "engineering_orchestrator": {"port": 8787, "path": "/readyz"},
    "ollama": {"port": 11434, "path": "/api/tags"},
}


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
            None,
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
    return {"resolved": bool(addresses), "address_count": len(addresses)}


def tcp_port_reachable(port: int) -> bool:
    try:
        with socket.create_connection((TARGET_HOST, port), timeout=TCP_TIMEOUT_SECONDS):
            return True
    except OSError:
        return False


def http_status(port: int, path: str) -> int | None:
    request = urllib.request.Request(
        f"http://{TARGET_HOST}:{port}{path}",
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (urllib.error.URLError, OSError):
        return None


def probe_surfaces() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, config in SURFACES.items():
        port = int(config["port"])
        path = str(config["path"])
        reachable = tcp_port_reachable(port)
        result[name] = {
            "port": port,
            "tcp_reachable": reachable,
            "http_status": http_status(port, path) if reachable else None,
        }
    return result


def probe(confirm: str, correlation_id: str) -> dict[str, Any]:
    correlation_id = validate_request(confirm, correlation_id)
    source_host = validate_host()
    resolution = resolve_target()

    surfaces = {
        name: {"port": int(config["port"]), "tcp_reachable": False, "http_status": None}
        for name, config in SURFACES.items()
    }
    if resolution["resolved"]:
        surfaces = probe_surfaces()

    open_surfaces = sorted(
        name for name, state in surfaces.items() if state["tcp_reachable"] is True
    )
    non_orchestrator = [
        name for name in open_surfaces if name != "engineering_orchestrator"
    ]
    return {
        "ok": True,
        "probe_completed": True,
        "probe_revision": PROBE_REVISION,
        "source_host": source_host,
        "target_host": TARGET_HOST,
        "dns_resolved": resolution["resolved"],
        "resolved_address_count": resolution["address_count"],
        "surfaces": surfaces,
        "open_surfaces": open_surfaces,
        "non_orchestrator_surfaces": non_orchestrator,
        "recovery_actuator_proven": False,
        "forbidden_transports_probed": False,
        "remote_shell_used": False,
        "credentials_supplied": False,
        "production_touched": False,
        "secrets_read": False,
        "correlation_id": correlation_id,
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
    except (ProbeError, OSError):
        payload = {
            "ok": False,
            "probe_completed": False,
            "probe_revision": PROBE_REVISION,
            "source_host": socket.gethostname(),
            "target_host": TARGET_HOST,
            "correlation_id": args.correlation_id,
            "error_code": "probe_failed",
            "forbidden_transports_probed": False,
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
