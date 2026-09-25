#!/usr/bin/env python3
"""Sonda governada e somente leitura de superfícies runtime Noteri -> Desktop."""

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
PROBE_REVISION = "runtime-surfaces-v2"
TCP_TIMEOUT_SECONDS = 1.5
HTTP_TIMEOUT_SECONDS = 3.0

SURFACES = {
    "reqsys_dev_gateway": {"port": 8083, "path": "/api/health"},
    "codex_backend": {"port": 8000, "path": "/health"},
    "codex_gateway": {"port": 8008, "path": "/health"},
    "engineering_worker_pool": {"port": 8097, "path": "/health"},
    "engineering_orchestrator": {"port": 8787, "path": "/readyz"},
    "ollama": {"port": 11434, "path": "/api/tags"},
    "docker_engine_http": {"port": 2375, "path": "/version"},
    "docker_engine_tls": {"port": 2376, "path": None},
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


def system32_executable(name: str) -> Path | None:
    root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    target = root / "System32" / name
    return target if target.is_file() else None


def parse_visible_share_count(stdout: str) -> int:
    """Conta linhas de shares visíveis sem persistir nomes."""
    separator_seen = False
    count = 0
    for raw_line in (stdout or "").splitlines():
        line = raw_line.strip()
        if not separator_seen:
            if len(line) >= 3 and set(line) == {"-"}:
                separator_seen = True
            continue
        if not line:
            continue
        lowered = line.casefold()
        if lowered.startswith(
            (
                "the command",
                "o comando",
                "there are no",
                "não há",
                "nao ha",
            )
        ):
            continue
        if set(line) == {"-"}:
            continue
        count += 1
    return count


def probe_visible_smb_shares() -> dict[str, Any]:
    """Enumera somente shares não administrativos visíveis via NET VIEW.

    Nenhum nome de share, stdout ou stderr é persistido.
    """
    executable = system32_executable("net.exe")
    if executable is None:
        return {"status": "dependency_unavailable", "visible_share_count": 0}
    try:
        completed = subprocess.run(
            [str(executable), "view", rf"\\{TARGET_HOST}"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "visible_share_count": 0}
    except OSError:
        return {"status": "dependency_unavailable", "visible_share_count": 0}

    combined = f"{completed.stdout}\n{completed.stderr}".casefold()
    if completed.returncode == 0:
        return {
            "status": "accessible",
            "visible_share_count": parse_visible_share_count(completed.stdout),
        }
    if any(
        marker in combined
        for marker in (
            "access is denied",
            "acesso negado",
            "system error 5",
            "erro de sistema 5",
        )
    ):
        return {"status": "access_denied", "visible_share_count": 0}
    return {"status": "unavailable", "visible_share_count": 0}


def probe_surfaces() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, config in SURFACES.items():
        port = int(config["port"])
        path = config.get("path")
        reachable = tcp_port_reachable(port)
        result[name] = {
            "port": port,
            "tcp_reachable": reachable,
            "http_status": (
                http_status(port, str(path))
                if reachable and isinstance(path, str) and path
                else None
            ),
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
    smb_probe = {"status": "not_probed", "visible_share_count": 0}
    if resolution["resolved"]:
        surfaces = probe_surfaces()
        smb_probe = probe_visible_smb_shares()

    open_surfaces = sorted(
        name for name, state in surfaces.items() if state["tcp_reachable"] is True
    )
    non_orchestrator = [
        name for name in open_surfaces if name != "engineering_orchestrator"
    ]
    docker_status = surfaces["docker_engine_http"]["http_status"]
    docker_remote_api_candidate = (
        isinstance(docker_status, int) and 200 <= docker_status < 300
    )
    smb_non_admin_transport_candidate = (
        smb_probe["status"] == "accessible"
        and int(smb_probe["visible_share_count"]) > 0
    )
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
        "smb_visible_share_probe": smb_probe,
        "smb_non_admin_transport_candidate": smb_non_admin_transport_candidate,
        "docker_remote_api_candidate": docker_remote_api_candidate,
        "remote_write_attempted": False,
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