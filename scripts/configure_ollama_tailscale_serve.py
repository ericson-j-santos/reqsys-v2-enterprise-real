#!/usr/bin/env python3
"""Configura Ollama privado via Tailscale Serve sem expor a porta nativa."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BACKEND = "http://127.0.0.1:11434"
DEFAULT_HTTPS_PORT = 11443
TIMEOUT_SECONDS = 20


class ServeError(RuntimeError):
    pass


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def find_tailscale() -> Path:
    found = shutil.which("tailscale")
    if found:
        return Path(found)
    candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale" / "tailscale.exe"
    if candidate.is_file():
        return candidate
    raise ServeError("tailscale_cli_not_found")


def run_tailscale(binary: Path, args: list[str], *, timeout: int = TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(binary), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        shell=False,
    )
    return result


def require_ok(result: subprocess.CompletedProcess[str], action: str) -> str:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-1000:]
        raise ServeError(f"{action}_failed rc={result.returncode} detail={detail}")
    return (result.stdout or "").strip()


def read_json_url(url: str, timeout: int = TIMEOUT_SECONDS) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise ServeError(f"http_status_{response.status}:{url}")
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise ServeError(f"http_probe_failed:{url}:{type(exc).__name__}") from exc
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ServeError(f"invalid_json_object:{url}")
    return data


def validate_backend(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized != DEFAULT_BACKEND:
        raise ServeError("backend_must_remain_loopback_127_0_0_1_11434")
    return normalized


def tailscale_status(binary: Path) -> dict[str, Any]:
    raw = require_ok(run_tailscale(binary, ["status", "--json"]), "tailscale_status")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ServeError("tailscale_status_invalid_json")
    return data


def serve_status(binary: Path) -> dict[str, Any]:
    result = run_tailscale(binary, ["serve", "status", "--json"])
    if result.returncode != 0:
        return {"available": False, "raw": (result.stderr or result.stdout or "").strip()[-1000:]}
    raw = (result.stdout or "").strip()
    if not raw:
        return {"available": True, "config": {}}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"available": True, "raw": raw[-2000:]}
    return {"available": True, "config": parsed}


def dns_name(status: dict[str, Any]) -> str:
    self_info = status.get("Self")
    if not isinstance(self_info, dict):
        raise ServeError("tailscale_self_missing")
    value = str(self_info.get("DNSName") or "").strip().rstrip(".")
    if not value:
        raise ServeError("tailscale_dns_name_missing")
    return value


def tailscale_ips(status: dict[str, Any]) -> list[str]:
    self_info = status.get("Self")
    if not isinstance(self_info, dict):
        return []
    values = self_info.get("TailscaleIPs")
    return [str(value) for value in values] if isinstance(values, list) else []


def local_non_loopback_ipv4() -> list[str]:
    values: set[str] = set()
    try:
        rows = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        rows = []
    for row in rows:
        raw = str(row[4][0])
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if addr.version == 4 and not addr.is_loopback and not addr.is_link_local and not addr.is_unspecified:
            values.add(raw)
    return sorted(values)


def direct_port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def backend_inventory(base_url: str) -> dict[str, Any]:
    version = read_json_url(f"{base_url}/api/version")
    models = read_json_url(f"{base_url}/v1/models")
    items = models.get("data")
    names = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                names.append(str(item["id"]))
    return {"version": version.get("version"), "models": names}


def validate_private_path(binary: Path, base_url: str, https_port: int) -> dict[str, Any]:
    status = tailscale_status(binary)
    if str(status.get("BackendState") or "").casefold() != "running":
        raise ServeError("tailscale_not_running")
    inventory = backend_inventory(base_url)
    dns = dns_name(status)
    serve_base = f"https://{dns}:{https_port}"
    remote_version = read_json_url(f"{serve_base}/api/version")
    remote_models = read_json_url(f"{serve_base}/v1/models")
    exposed = [host for host in local_non_loopback_ipv4() if direct_port_open(host, 11434)]
    if exposed:
        raise ServeError("ollama_native_port_exposed_non_loopback:" + ",".join(exposed))
    return {
        "ok": True,
        "provider": "Ollama",
        "api_key_placeholder": "ollama",
        "host": f"{serve_base}/v1",
        "serve_base": serve_base,
        "tailscale_dns_name": dns,
        "tailscale_ips": tailscale_ips(status),
        "ollama_version": inventory["version"],
        "models": inventory["models"],
        "remote_version": remote_version.get("version"),
        "remote_model_count": len(remote_models.get("data") or []),
        "native_ollama_non_loopback_open": False,
        "serve": serve_status(binary),
    }


def configure(binary: Path, base_url: str, https_port: int) -> dict[str, Any]:
    backend_inventory(base_url)
    status = tailscale_status(binary)
    if str(status.get("BackendState") or "").casefold() != "running":
        raise ServeError("tailscale_not_running")
    command = [
        "serve",
        "--bg",
        "--yes",
        f"--https={https_port}",
        base_url,
    ]
    require_ok(run_tailscale(binary, command, timeout=60), "tailscale_serve_configure")
    return validate_private_path(binary, base_url, https_port)


def disable(binary: Path, https_port: int) -> dict[str, Any]:
    require_ok(
        run_tailscale(binary, ["serve", f"--https={https_port}", "off"], timeout=30),
        "tailscale_serve_disable",
    )
    return {"ok": True, "disabled_https_port": https_port, "serve": serve_status(binary)}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("status", "configure", "validate", "disable"))
    p.add_argument("--backend", default=DEFAULT_BACKEND)
    p.add_argument("--https-port", type=int, default=DEFAULT_HTTPS_PORT)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        base_url = validate_backend(args.backend)
        if args.https_port < 1 or args.https_port > 65535:
            raise ServeError("invalid_https_port")
        binary = find_tailscale()
        if args.command == "status":
            payload = {
                "ok": True,
                "tailscale": tailscale_status(binary),
                "serve": serve_status(binary),
                "backend": backend_inventory(base_url),
            }
        elif args.command == "configure":
            payload = configure(binary, base_url, args.https_port)
        elif args.command == "validate":
            payload = validate_private_path(binary, base_url, args.https_port)
        else:
            payload = disable(binary, args.https_port)
        emit(payload)
        return 0
    except (ServeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
