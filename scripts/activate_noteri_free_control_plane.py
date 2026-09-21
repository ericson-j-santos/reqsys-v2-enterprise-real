#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

EXPECTED_HOST = "Noteri"
WATCHDOG = Path(__file__).resolve().parent / "noteri_control_plane_watchdog.py"
CONFIRM = "ACTIVATE-NOTERI-FREE-CONTROL-PLANE"
INSTALL_CONFIRM = "INSTALL-NOTERI-CONTROL-PLANE-WATCHDOG"

CANDIDATES = (
    Path(r"C:\actions-runner"),
    Path(r"C:\dev\actions-runner"),
    Path(r"C:\dev\github-actions-runner"),
    Path(r"C:\dev\runner"),
)

def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))

def validate_host() -> str:
    if os.name != "nt":
        raise RuntimeError("Windows obrigatório")
    host = socket.gethostname()
    if host.casefold() != EXPECTED_HOST.casefold():
        raise RuntimeError(f"host não autorizado: {host}")
    return host

def runner_contract(root: Path) -> bool:
    return (
        root.is_dir()
        and (root / ".runner").is_file()
        and (root / "run.cmd").is_file()
        and (root / "bin" / "Runner.Listener.exe").is_file()
    )

def discover_runner(explicit: Path | None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("REQSYS_GITHUB_RUNNER_HOME")
    if env:
        candidates.append(Path(env))
    candidates.extend(CANDIDATES)
    for base in (Path.home(), Path(r"C:\dev")):
        if not base.is_dir():
            continue
        try:
            for item in base.iterdir():
                if item.is_dir() and "runner" in item.name.casefold():
                    candidates.append(item)
        except OSError:
            pass
    seen: set[str] = set()
    for item in candidates:
        key = os.path.normcase(str(item))
        if key in seen:
            continue
        seen.add(key)
        try:
            if runner_contract(item):
                return item.resolve()
        except OSError:
            continue
    return None

def runner_running() -> bool:
    target = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "tasklist.exe"
    cp = subprocess.run(
        [str(target), "/FI", "IMAGENAME eq Runner.Listener.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    return cp.returncode == 0 and "runner.listener.exe" in cp.stdout.casefold()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-sha")
    parser.add_argument("--runner-home", type=Path)
    args = parser.parse_args()
    if args.confirm != CONFIRM:
        emit({"ok": False, "error": "confirmation_invalid"})
        return 2
    try:
        host = validate_host()
        repo_root = args.repo_root.resolve()
        source_sha = (args.source_sha or "").strip()
        if not source_sha:
            cp = subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=20, check=False,
            )
            if cp.returncode != 0:
                raise RuntimeError("source_sha indisponível")
            source_sha = cp.stdout.strip()
        if len(source_sha) != 40:
            raise RuntimeError("source_sha inválido")

        runner = discover_runner(args.runner_home)
        if runner is None:
            emit({
                "ok": False,
                "state": "runner_registration_required",
                "host": host,
                "rdc_required": False,
                "production_touched": False,
                "secrets_read": False,
            })
            return 4

        cp = subprocess.run(
            [
                sys.executable, str(WATCHDOG), "install",
                "--repo-root", str(repo_root),
                "--runner-home", str(runner),
                "--source-sha", source_sha,
                "--confirm", INSTALL_CONFIRM,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        )
        payload: dict[str, Any] = {}
        for line in reversed(cp.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    pass
        running = runner_running()
        result = {
            "ok": bool(running),
            "host": host,
            "runner_home": str(runner),
            "runner_running": running,
            "watchdog_exit_code": cp.returncode,
            "watchdog_runtime_ok": bool(payload.get("runtime_ok")),
            "watchdog_activation_pending": bool(payload.get("activation_pending")),
            "watchdog_task": payload.get("task"),
            "source_sha": source_sha,
            "rdc_required": False,
            "production_touched": False,
            "secrets_read": False,
        }
        emit(result)
        return 0 if running else 3
    except Exception as exc:
        emit({
            "ok": False,
            "error": str(exc)[:1000],
            "error_type": type(exc).__name__,
            "rdc_required": False,
            "production_touched": False,
            "secrets_read": False,
        })
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
