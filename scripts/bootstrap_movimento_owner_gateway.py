#!/usr/bin/env python3
"""Instala e mantém o Owner Data Gateway no PC24x7 sem depender de shell externo."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "services" / "movimento-owner-gateway" / "server.py"
OWNER_SOURCE = ROOT / "scripts" / "movimento_email_owner_source.py"
RUNTIME = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ReqSys" / "OwnerGateway"
CONFIG = RUNTIME / "config.json"
TOKEN = RUNTIME / "service.token"
SERVER_RUNTIME = RUNTIME / "server.py"
OWNER_RUNTIME = RUNTIME / "owner_source.py"
LOG = RUNTIME / "gateway.log"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "ReqSysOwnerDataGateway"


def _load_server_module(path: Path):
    spec = importlib.util.spec_from_file_location("movimento_owner_gateway_server", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("gateway_server_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _health(bind_ip: str, port: int, timeout: float = 2.0) -> dict:
    url = f"http://{bind_ip}:{port}/health"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _running(bind_ip: str, port: int) -> bool:
    try:
        return _health(bind_ip, port).get("status") == "ok"
    except Exception:
        return False


def _pythonw() -> str:
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return str(candidate if candidate.is_file() else Path(sys.executable))


def _run_command(config_path: Path) -> list[str]:
    return [_pythonw(), str(SERVER_RUNTIME), "--config", str(config_path)]


def _register_autostart(command: list[str]) -> None:
    if os.name != "nt":
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command))


def _autostart_registered() -> bool:
    if os.name != "nt":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, RUN_NAME)
        return bool(str(value).strip())
    except OSError:
        return False


def _start(command: list[str]) -> int:
    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    log = LOG.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        command,
        cwd=RUNTIME,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        close_fds=True,
        creationflags=creationflags,
    )
    return int(proc.pid)


def install(port: int) -> dict:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    server_module = _load_server_module(SERVER)
    bind_ip = server_module.detect_overlay_ipv4()

    shutil.copy2(SERVER, SERVER_RUNTIME)
    shutil.copy2(OWNER_SOURCE, OWNER_RUNTIME)

    created_token = False
    if not TOKEN.is_file() or len(TOKEN.read_text(encoding="utf-8").strip()) < 32:
        TOKEN.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        created_token = True

    config = {
        "schema_version": "1.0.0",
        "logical_name": "reqsys-owner-data-gateway",
        "node_name": socket.gethostname(),
        "bind_ip": bind_ip,
        "port": port,
        "token_file": str(TOKEN),
        "owner_module": str(OWNER_RUNTIME),
        "runtime_dir": str(RUNTIME),
        "source_db": "ReqSysMovimentoOwnerDev",
        "target_db": "ReqSysMovimentoDev",
    }
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    command = _run_command(CONFIG)
    _register_autostart(command)

    already_running = _running(bind_ip, port)
    pid = None
    if not already_running:
        pid = _start(command)
        for _ in range(20):
            time.sleep(0.25)
            if _running(bind_ip, port):
                break

    healthy = _running(bind_ip, port)
    return {
        "status": "passed" if healthy else "blocked",
        "logical_name": config["logical_name"],
        "node_name": config["node_name"],
        "private_bind_hash": hashlib.sha256(bind_ip.encode("utf-8")).hexdigest()[:16],
        "port": port,
        "token_created": created_token,
        "token_sha256": hashlib.sha256(TOKEN.read_bytes()).hexdigest(),
        "autostart": _autostart_registered(),
        "already_running": already_running,
        "pid_started": pid,
        "secrets_exposed": False,
        "production_touched": False,
    }


def status() -> dict:
    if not CONFIG.is_file():
        return {"status": "not_installed", "production_touched": False}
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    healthy = _running(str(config["bind_ip"]), int(config["port"]))
    return {
        "status": "passed" if healthy else "blocked",
        "logical_name": config["logical_name"],
        "node_name": config.get("node_name"),
        "private_bind_hash": hashlib.sha256(str(config["bind_ip"]).encode("utf-8")).hexdigest()[:16],
        "port": int(config["port"]),
        "token_present": TOKEN.is_file(),
        "autostart_registered": _autostart_registered(),
        "secrets_exposed": False,
        "production_touched": False,
    }


def probe() -> dict:
    if not CONFIG.is_file() or not TOKEN.is_file():
        return {"status": "not_installed", "production_touched": False}
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    token = TOKEN.read_text(encoding="utf-8").strip()
    request = urllib.request.Request(
        f"http://{config['bind_ip']}:{int(config['port'])}/status",
        method="GET",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            "status": "blocked",
            "error": type(exc).__name__,
            "authenticated_probe": False,
            "secrets_exposed": False,
            "production_touched": False,
        }
    return {
        "status": "passed" if payload.get("status") == "passed" else "blocked",
        "authenticated_probe": True,
        "source_authority": payload.get("source_authority"),
        "source_objects": payload.get("source_objects"),
        "target_objects": payload.get("target_objects"),
        "secrets_exposed": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("install", "status", "probe"))
    parser.add_argument("--port", type=int, default=18443)
    args = parser.parse_args()
    if not (1024 <= args.port <= 65535):
        raise SystemExit("port_invalid")
    if args.command == "install":
        result = install(args.port)
    elif args.command == "status":
        result = status()
    else:
        result = probe()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
