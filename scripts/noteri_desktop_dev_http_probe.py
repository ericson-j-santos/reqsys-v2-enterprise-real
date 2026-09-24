#!/usr/bin/env python3
"""Sonda HTTP governada e somente leitura do Noteri para o ReqSys DEV no Desktop."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
DEV_GATEWAY_PORT = 8083
CONFIRM = "PROBE-NOTERI-DESKTOP-DEV-HTTP"
TCP_TIMEOUT_SECONDS = 2.0
HTTP_TIMEOUT_SECONDS = 3.0
ALLOWED_PATHS = ("/api/health", "/api/runtime/health")


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
            DEV_GATEWAY_PORT,
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


def tcp_reachable() -> bool:
    try:
        with socket.create_connection(
            (TARGET_HOST, DEV_GATEWAY_PORT),
            timeout=TCP_TIMEOUT_SECONDS,
        ):
            return True
    except OSError:
        return False


def http_status(path: str) -> dict[str, Any]:
    if path not in ALLOWED_PATHS:
        raise ProbeError("path HTTP não autorizado")

    connection = http.client.HTTPConnection(
        TARGET_HOST,
        DEV_GATEWAY_PORT,
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    try:
        connection.request(
            "GET",
            path,
            headers={
                "Accept": "application/json",
                "User-Agent": "ReqSysNoteriDesktopDevHttpProbe/1.0",
            },
        )
        response = connection.getresponse()
        status = int(response.status)
        response.close()
        return {
            "transport_reachable": 100 <= status <= 599,
            "status": status,
            "error_type": None,
        }
    except (OSError, http.client.HTTPException) as exc:
        return {
            "transport_reachable": False,
            "status": None,
            "error_type": type(exc).__name__[:80],
        }
    finally:
        connection.close()


def probe(confirm: str, correlation_id: str) -> dict[str, Any]:
    correlation_id = validate_request(confirm, correlation_id)
    source_host = validate_host()
    resolution = resolve_target()

    tcp = False
    probes: dict[str, dict[str, Any]] = {
        path: {"transport_reachable": False, "status": None, "error_type": "not_attempted"}
        for path in ALLOWED_PATHS
    }

    if resolution["resolved"]:
        tcp = tcp_reachable()
        if tcp:
            probes = {path: http_status(path) for path in ALLOWED_PATHS}

    any_http = any(item["transport_reachable"] for item in probes.values())
    if not resolution["resolved"]:
        state = "name_resolution_failed"
    elif not tcp:
        state = "dev_gateway_tcp_closed"
    elif any_http:
        state = "dev_gateway_http_reachable"
    else:
        state = "dev_gateway_tcp_reachable_http_unresponsive"

    return {
        "ok": True,
        "probe_completed": True,
        "route": "reqsys_dev_http_8083",
        "source_host": source_host,
        "target_host": TARGET_HOST,
        "target_port": DEV_GATEWAY_PORT,
        "dns_resolved": resolution["resolved"],
        "resolved_address_count": resolution["address_count"],
        "tcp_reachable": tcp,
        "http_probes": probes,
        "network_state": state,
        "candidate_transport_reachable": bool(any_http),
        "correlation_id": correlation_id,
        "excluded_routes": ["wmi", "scm", "schtasks", "c$", "admin_broker"],
        "rdc_required": False,
        "remote_shell_used": False,
        "credentials_supplied": False,
        "mutating_request_sent": False,
        "uac_or_acl_relaxed": False,
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
    except (ProbeError, OSError, http.client.HTTPException) as exc:
        payload = {
            "ok": False,
            "probe_completed": False,
            "route": "reqsys_dev_http_8083",
            "source_host": socket.gethostname(),
            "target_host": TARGET_HOST,
            "target_port": DEV_GATEWAY_PORT,
            "correlation_id": args.correlation_id,
            "error": "probe_runtime_error",
            "error_type": type(exc).__name__[:80],
            "rdc_required": False,
            "remote_shell_used": False,
            "credentials_supplied": False,
            "mutating_request_sent": False,
            "uac_or_acl_relaxed": False,
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
