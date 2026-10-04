#!/usr/bin/env python3
"""Reconcilia o ingresso HTTPS do MCP Ollama no Desktop PC24x7.

Publica exclusivamente o bridge MCP loopback em 127.0.0.1:8010 sob /mcp por
Tailscale Funnel. Ollama :11434 e o gateway :8008 permanecem privados.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
MCP_TARGET = "http://127.0.0.1:8010"
MCP_PORT = 8010
MCP_PATH = "/mcp"
HTTPS_PORT = 443
TAILSCALE_CLI_ENV = "TAILSCALE_CLI_PATH"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class IngressError(RuntimeError):
    pass


def run(args: list[str], timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def require_host(hostname: str | None = None) -> str:
    host = hostname or socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise IngressError("host_not_authorized")
    return host


def resolve_tailscale_cli(
    source: Mapping[str, str] | None = None,
    *,
    which_fn: Callable[[str], str | None] | None = None,
) -> str:
    env = source if source is not None else os.environ
    configured = str(env.get(TAILSCALE_CLI_ENV, "")).strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.is_file():
            return str(configured_path)
        raise IngressError("TAILSCALE_CLI_CONFIGURED_PATH_INVALID")

    resolver = which_fn or shutil.which
    discovered = resolver("tailscale") or resolver("tailscale.exe")
    if discovered and Path(discovered).is_file():
        return str(Path(discovered))

    roots = []
    for key in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA"):
        root = str(env.get(key, "")).strip()
        if root and root not in roots:
            roots.append(root)
    for root in roots:
        candidate = Path(root) / "Tailscale" / "tailscale.exe"
        if candidate.is_file():
            return str(candidate)

    raise IngressError("TAILSCALE_CLI_NOT_FOUND")


def tailscale_status(tailscale_cli: str) -> dict[str, Any]:
    completed = run([tailscale_cli, "status", "--json"])
    if completed.returncode != 0:
        raise IngressError("tailscale_status_unavailable")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise IngressError("tailscale_status_invalid_json") from exc
    if not isinstance(payload, dict):
        raise IngressError("tailscale_status_invalid_shape")
    return payload


def stable_base_url(status: dict[str, Any]) -> str:
    dns_name = str(((status.get("Self") or {}).get("DNSName") or "")).strip().rstrip(".")
    if not dns_name or not dns_name.casefold().endswith(".ts.net"):
        raise IngressError("tailscale_dns_name_invalid")
    return f"https://{dns_name}"


def validate_tailscale_ready(status: dict[str, Any]) -> None:
    if status.get("BackendState") != "Running":
        raise IngressError("tailscale_backend_not_running")
    if not bool((status.get("CurrentTailnet") or {}).get("MagicDNSEnabled")):
        raise IngressError("tailscale_magicdns_required")


def local_mcp_ready(timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex(("127.0.0.1", MCP_PORT)) == 0


def funnel_status(tailscale_cli: str) -> dict[str, Any]:
    completed = run([tailscale_cli, "funnel", "status", "--json"])
    if completed.returncode != 0:
        return {"configured": False, "returncode": completed.returncode}
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {"configured": False, "returncode": completed.returncode, "invalid_json": True}
    return {"configured": True, "returncode": completed.returncode, "payload": payload}


def route_present(status: dict[str, Any]) -> bool:
    if not status.get("configured"):
        return False
    flattened = json.dumps(status.get("payload") or {}, ensure_ascii=True, sort_keys=True).casefold()
    target_present = "127.0.0.1:8010" in flattened or "localhost:8010" in flattened
    return target_present and MCP_PATH in flattened


def build_apply_command(tailscale_cli: str) -> list[str]:
    return [
        tailscale_cli,
        "funnel",
        "--bg",
        "--yes",
        f"--https={HTTPS_PORT}",
        f"--set-path={MCP_PATH}",
        MCP_TARGET,
    ]


def classify_apply_failure(completed: subprocess.CompletedProcess[str]) -> str:
    text = f"{completed.stdout}\n{completed.stderr}".casefold()
    consent_markers = (
        "login.tailscale.com",
        "enable funnel",
        "funnel node attribute",
        "funnel is not enabled",
    )
    if any(marker in text for marker in consent_markers):
        return "TAILSCALE_FUNNEL_CONSENT_REQUIRED"
    return "TAILSCALE_FUNNEL_APPLY_FAILED"


def apply_funnel(tailscale_cli: str) -> str | None:
    completed = run(build_apply_command(tailscale_cli), timeout=90)
    if completed.returncode != 0:
        return classify_apply_failure(completed)
    return None


def public_route_probe(url: str, timeout: float = 10.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": "ReqSysOllamaMcpIngress/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
    except (OSError, urllib.error.URLError) as exc:
        return {"reachable": False, "error": type(exc).__name__}

    # JSON-RPC vazio deve ser rejeitado pela aplicação; o objetivo aqui é provar
    # transporte/roteamento, não autenticar ou executar ferramenta.
    reachable = 200 <= status < 500 and status != 404
    return {"reachable": reachable, "status": status}


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingresso DEV do GitHub Copilot para Ollama MCP")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    payload: dict[str, Any] = {
        "schema_version": "1.0.1",
        "environment": "DEV",
        "provider": "tailscale_funnel",
        "source_sha": args.source_sha,
        "target": MCP_TARGET,
        "mount_path": MCP_PATH,
        "apply": bool(args.apply),
        "production_touched": False,
        "secrets_read": False,
        "ollama_direct_exposed": False,
        "gateway_direct_exposed": False,
        "tailscale_cli_resolved": False,
    }

    try:
        if not _SHA_RE.fullmatch(args.source_sha):
            raise IngressError("source_sha_invalid")
        payload["host"] = require_host()
        tailscale_cli = resolve_tailscale_cli()
        payload["tailscale_cli_resolved"] = True
        status = tailscale_status(tailscale_cli)
        validate_tailscale_ready(status)
        base_url = stable_base_url(status)
        payload["public_url"] = base_url + MCP_PATH

        local_ready = local_mcp_ready()
        payload["local_mcp_ready"] = local_ready
        if not local_ready:
            raise IngressError("MCP_LOCAL_NOT_READY")

        before = funnel_status(tailscale_cli)
        payload["route_before"] = route_present(before)
        if args.apply and not payload["route_before"]:
            failure = apply_funnel(tailscale_cli)
            if failure:
                raise IngressError(failure)

        after = funnel_status(tailscale_cli)
        payload["route_after"] = route_present(after)
        if not payload["route_after"]:
            raise IngressError("MCP_FUNNEL_ROUTE_NOT_OBSERVED")

        probe = public_route_probe(payload["public_url"])
        payload["public_probe"] = probe
        if not probe.get("reachable"):
            raise IngressError("MCP_PUBLIC_ROUTE_NOT_REACHABLE")

        payload["ready"] = True
        write_evidence(args.evidence_file, payload)
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        return 0
    except (IngressError, OSError, subprocess.SubprocessError, ValueError) as exc:
        payload["ready"] = False
        payload["error"] = (
            exc.args[0]
            if isinstance(exc, IngressError) and exc.args and isinstance(exc.args[0], str)
            else "ingress_runtime_error"
        )
        payload["error_type"] = type(exc).__name__
        write_evidence(args.evidence_file, payload)
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
