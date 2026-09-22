#!/usr/bin/env python3
"""Diagnóstico sanitizado de DNS/TCP para uma origem SQL corporativa."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
from typing import Any

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def probe(server: str, port: int = 1433, timeout: float = 4.0) -> dict[str, Any]:
    if not _SAFE_NAME.fullmatch(server):
        raise ValueError("invalid_server")
    if port < 1 or port > 65535:
        raise ValueError("invalid_port")

    evidence: dict[str, Any] = {
        "schema_version": "1.0.0",
        "feature": "sql_network_route_probe",
        "server_hash": _hash(server),
        "port": port,
        "secret_used": False,
        "sql_executed": False,
        "dns_resolved": False,
        "resolved_address_hashes": [],
        "tcp_reachable": False,
        "passed": False,
    }

    try:
        infos = socket.getaddrinfo(server, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        evidence["dns_error_type"] = type(exc).__name__
        evidence["dns_error_code"] = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
        return evidence

    addresses = sorted({str(info[4][0]) for info in infos})
    evidence["dns_resolved"] = bool(addresses)
    evidence["resolved_address_hashes"] = [_hash(address) for address in addresses]

    try:
        with socket.create_connection((server, port), timeout=timeout):
            evidence["tcp_reachable"] = True
    except OSError as exc:
        evidence["tcp_error_type"] = type(exc).__name__
        evidence["tcp_error_code"] = getattr(exc, "winerror", None) or getattr(exc, "errno", None)

    evidence["passed"] = bool(evidence["dns_resolved"] and evidence["tcp_reachable"])
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--port", type=int, default=1433)
    args = parser.parse_args()
    try:
        result = probe(args.server, args.port)
    except Exception as exc:
        result = {
            "schema_version": "1.0.0",
            "feature": "sql_network_route_probe",
            "server_hash": _hash(args.server),
            "port": args.port,
            "secret_used": False,
            "sql_executed": False,
            "dns_resolved": False,
            "tcp_reachable": False,
            "passed": False,
            "error_type": type(exc).__name__,
        }
        print(json.dumps(result, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
