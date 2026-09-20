#!/usr/bin/env python3
"""Instala/remove supervisor DEV recorrente no Task Scheduler do usuário.

A instalação materializa uma cópia persistente fora do worktree para que a
automação continue válida após limpeza de branches/worktrees.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TASK_NAME = "ReqSys-Dev-Runtime-Supervisor"
ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCRIPTS = (
    "pc24x7_dev_runtime_supervisor.py",
    "pc24x7_public_dev_tunnel.py",
    "pc24x7_tailscale_funnel.py",
)
BASE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ReqSys"
RUNTIME_DIR = BASE_DIR / "RuntimeSupervisor"
SCRIPTS_DIR = RUNTIME_DIR / "scripts"
LOG_DIR = BASE_DIR / "PublicRuntime"
PERSISTENT_SUPERVISOR = SCRIPTS_DIR / "pc24x7_dev_runtime_supervisor.py"
WRAPPER = LOG_DIR / "run-dev-supervisor.cmd"
MANIFEST = RUNTIME_DIR / "manifest.json"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def source_head() -> str | None:
    completed = run(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
    return completed.stdout.strip() if completed.returncode == 0 else None


def materialize_runtime() -> dict[str, str]:
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for name in SOURCE_SCRIPTS:
        source = ROOT / "scripts" / name
        target = SCRIPTS_DIR / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, target)
        copied[name] = str(target)

    payload = {
        "schema_version": "1.0.0",
        "source_head": source_head(),
        "source_root": str(ROOT),
        "supervisor": str(PERSISTENT_SUPERVISOR),
    }
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return copied


def write_wrapper() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    python = Path(sys.executable)
    content = (
        "@echo off\r\n"
        f'"{python}" "{PERSISTENT_SUPERVISOR}" --apply '
        f'>> "{LOG_DIR / "dev-supervisor.log"}" 2>&1\r\n'
    )
    WRAPPER.write_text(content, encoding="utf-8")


def install() -> int:
    copied = materialize_runtime()
    write_wrapper()
    command = [
        "schtasks", "/Create", "/F",
        "/TN", TASK_NAME,
        "/TR", str(WRAPPER),
        "/SC", "MINUTE", "/MO", "5",
    ]
    created = run(command)
    if created.returncode != 0:
        print(created.stderr or created.stdout, file=sys.stderr)
        return 2

    triggered = run(["schtasks", "/Run", "/TN", TASK_NAME])
    print(json.dumps({
        "status": "installed",
        "task": TASK_NAME,
        "wrapper": str(WRAPPER),
        "persistent_supervisor": str(PERSISTENT_SUPERVISOR),
        "copied": copied,
        "trigger_returncode": triggered.returncode,
    }, ensure_ascii=False, sort_keys=True))
    return 0


def uninstall() -> int:
    deleted = run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME])
    if WRAPPER.exists():
        WRAPPER.unlink()
    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)
    if deleted.returncode not in (0, 1):
        print(deleted.stderr or deleted.stdout, file=sys.stderr)
        return 2
    print(f"REMOVED {TASK_NAME}")
    return 0


def status() -> int:
    result = run(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"])
    manifest = None
    if MANIFEST.is_file():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    print(json.dumps({
        "task_query_returncode": result.returncode,
        "task": result.stdout if result.stdout else result.stderr,
        "manifest": manifest,
        "wrapper_exists": WRAPPER.is_file(),
        "persistent_supervisor_exists": PERSISTENT_SUPERVISOR.is_file(),
    }, ensure_ascii=False, sort_keys=True))
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("install")
    sub.add_parser("uninstall")
    sub.add_parser("status")
    args = parser.parse_args()
    return {"install": install, "uninstall": uninstall, "status": status}[args.action]()


if __name__ == "__main__":
    raise SystemExit(main())
