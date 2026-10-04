#!/usr/bin/env python3
"""Probe governado e mínimo de conectividade entre hosts PC24x7.

Não lê credenciais, não altera firewall e não executa shell. O modo serve-once
abre um listener efêmero que aceita exatamente uma conexão e encerra.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import socket
from typing import Any


MAX_MARKER_BYTES = 256


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def _safe_ipv4(values: list[str]) -> list[str]:
    result: list[str] = []
    for raw in values:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if address.version != 4:
            continue
        if address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
            continue
        value = str(address)
        if value not in result:
            result.append(value)
    return sorted(result)


def resolve_ipv4(host: str) -> list[str]:
    rows = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    return _safe_ipv4([str(row[4][0]) for row in rows])


def local_ipv4() -> list[str]:
    return resolve_ipv4(socket.gethostname())


def serve_once(bind_host: str, port: int, marker: str, timeout: float) -> dict[str, Any]:
    if not marker or len(marker.encode("utf-8")) > MAX_MARKER_BYTES:
        raise ValueError("marker inválido")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.settimeout(timeout)
        server.bind((bind_host, port))
        server.listen(1)
        actual_host, actual_port = server.getsockname()
        _emit(
            {
                "ok": True,
                "mode": "serve-once",
                "state": "listening",
                "bind_host": actual_host,
                "port": actual_port,
            }
        )
        conn, peer = server.accept()
        with conn:
            conn.settimeout(timeout)
            raw = conn.recv(MAX_MARKER_BYTES + 2)
            received = raw.decode("utf-8", errors="strict").strip()
            matched = received == marker
            response = {
                "ok": matched,
                "mode": "serve-once",
                "state": "completed",
                "marker_matched": matched,
                "peer_ipv4": str(peer[0]),
            }
            conn.sendall((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))
            return response


def connect_once(host: str, port: int, marker: str, timeout: float) -> dict[str, Any]:
    if not marker or len(marker.encode("utf-8")) > MAX_MARKER_BYTES:
        raise ValueError("marker inválido")
    resolved = resolve_ipv4(host)
    with socket.create_connection((host, port), timeout=timeout) as client:
        client.settimeout(timeout)
        client.sendall((marker + "\n").encode("utf-8"))
        raw = client.recv(2048)
    payload = json.loads(raw.decode("utf-8"))
    matched = bool(payload.get("ok")) and payload.get("marker_matched") is True
    return {
        "ok": matched,
        "mode": "connect",
        "host": host,
        "port": port,
        "resolved_ipv4": resolved,
        "marker_matched": matched,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe de conectividade PC24x7 sem shell")
    sub = parser.add_subparsers(dest="mode", required=True)

    sub.add_parser("local", help="Lista IPv4 locais elegíveis.")

    resolve = sub.add_parser("resolve", help="Resolve um hostname para IPv4.")
    resolve.add_argument("--host", required=True)

    serve = sub.add_parser("serve-once", help="Aceita uma única conexão e encerra.")
    serve.add_argument("--bind-host", default="")
    serve.add_argument("--port", type=int, default=18097)
    serve.add_argument("--marker", required=True)
    serve.add_argument("--timeout", type=float, default=20.0)

    connect = sub.add_parser("connect", help="Valida handshake com listener serve-once.")
    connect.add_argument("--host", required=True)
    connect.add_argument("--port", type=int, default=18097)
    connect.add_argument("--marker", required=True)
    connect.add_argument("--timeout", type=float, default=10.0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.mode == "local":
            addresses = local_ipv4()
            _emit({"ok": bool(addresses), "mode": "local", "host": socket.gethostname(), "ipv4": addresses})
            return 0 if addresses else 3
        if args.mode == "resolve":
            addresses = resolve_ipv4(args.host)
            _emit({"ok": bool(addresses), "mode": "resolve", "host": args.host, "ipv4": addresses})
            return 0 if addresses else 3
        if args.mode == "serve-once":
            bind_host = args.bind_host.strip()
            if not bind_host:
                addresses = local_ipv4()
                if not addresses:
                    raise RuntimeError("nenhum IPv4 local elegível")
                bind_host = addresses[0]
            result = serve_once(bind_host, args.port, args.marker, args.timeout)
            _emit(result)
            return 0 if result["ok"] else 4
        if args.mode == "connect":
            result = connect_once(args.host, args.port, args.marker, args.timeout)
            _emit(result)
            return 0 if result["ok"] else 4
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        _emit({"ok": False, "mode": args.mode, "error": type(exc).__name__})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
