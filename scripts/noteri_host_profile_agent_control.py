#!/usr/bin/env python3
"""Controla o agente local de perfil do Noteri sem expor shell ou porta remota."""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SERVICE_NAME = "noteri-host-profile-agent"
DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8765


def runtime_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "ReqSys" / "TodoGlobal24x7"
    return Path.home() / ".config" / "todo-global-24x7"


def state_path() -> Path:
    return runtime_dir() / "host-profile-agent.json"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def probe(port: int = DEFAULT_PORT, timeout: float = 1.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return None
    if payload.get("service") != SERVICE_NAME:
        return None
    return payload


def _validate_origin(origin: str) -> str:
    value = origin.strip().rstrip("/")
    if not value:
        raise ValueError("origin vazio")
    if "*" in value:
        raise ValueError("origin curinga não é permitido")
    if not (value.startswith("http://") or value.startswith("https://")):
        raise ValueError("origin deve usar http ou https")
    return value


def build_command(
    *,
    host: str,
    port: int,
    origins: list[str],
    profile_path: Path | None = None,
    audit_path: Path | None = None,
) -> list[str]:
    agent_script = Path(__file__).resolve().with_name("noteri_host_profile_agent.py")
    if not agent_script.is_file():
        raise FileNotFoundError(f"agente local ausente: {agent_script}")
    command = [
        sys.executable,
        str(agent_script),
        "--bind",
        DEFAULT_BIND,
        "--port",
        str(port),
        "--host",
        host,
    ]
    if profile_path is not None:
        command.extend(["--profile-path", str(profile_path)])
    if audit_path is not None:
        command.extend(["--audit-path", str(audit_path)])
    for origin in origins:
        command.extend(["--allow-origin", _validate_origin(origin)])
    return command


def start_agent(
    *,
    host: str,
    port: int,
    origins: list[str],
    profile_path: Path | None = None,
    audit_path: Path | None = None,
    state_file: Path | None = None,
) -> dict[str, Any]:
    current_host = socket.gethostname()
    if current_host.casefold() != host.strip().casefold():
        raise RuntimeError(f"host atual não corresponde ao alvo: {current_host}")

    existing = probe(port)
    if existing:
        if str(existing.get("host") or "").casefold() != current_host.casefold():
            raise RuntimeError("porta local ocupada por agente de outro host")
        return {
            "ok": True,
            "status": "running",
            "reused": True,
            "host": current_host,
            "port": port,
            "loopback_only": True,
        }

    command = build_command(
        host=host,
        port=port,
        origins=origins,
        profile_path=profile_path,
        audit_path=audit_path,
    )
    kwargs: dict[str, Any] = {
        "cwd": str(Path(__file__).resolve().parents[1]),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True

    process = subprocess.Popen(command, **kwargs)
    deadline = time.monotonic() + 8.0
    observed = None
    while time.monotonic() < deadline:
        observed = probe(port)
        if observed:
            break
        if process.poll() is not None:
            break
        time.sleep(0.2)
    if not observed:
        raise RuntimeError("agente local não ficou saudável após inicialização")
    if str(observed.get("host") or "").casefold() != current_host.casefold():
        raise RuntimeError("health do agente retornou host divergente")

    state = {
        "schema_version": "1",
        "service": SERVICE_NAME,
        "host": current_host,
        "pid": process.pid,
        "port": port,
        "bind": DEFAULT_BIND,
        "loopback_only": True,
        "origins": origins,
        "started_at_epoch": int(time.time()),
        "script": str(Path(command[1]).resolve()),
    }
    if profile_path is not None:
        state["profile_path"] = str(profile_path)
    if audit_path is not None:
        state["audit_path"] = str(audit_path)
    _atomic_write(state_file or state_path(), state)
    return {"ok": True, "status": "running", "reused": False, **state}


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlador do agente local NORMAL/ESTUDO")
    parser.add_argument("command", choices=["start", "status"])
    parser.add_argument("--host", default="Noteri")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--allow-origin", action="append", default=[])
    parser.add_argument("--profile-path", type=Path)
    parser.add_argument("--audit-path", type=Path)
    parser.add_argument("--state-path", type=Path)
    args = parser.parse_args()

    try:
        if args.command == "status":
            health = probe(args.port)
            if not health:
                print(json.dumps({"ok": False, "status": "stopped", "port": args.port}, ensure_ascii=False))
                return 3
            print(json.dumps({"ok": True, "status": "running", **health}, ensure_ascii=False, sort_keys=True))
            return 0
        result = start_agent(
            host=args.host,
            port=args.port,
            origins=args.allow_origin,
            profile_path=args.profile_path,
            audit_path=args.audit_path,
            state_file=args.state_path,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
