from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is required")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def copy_runtime(source_root: Path, install_root: Path) -> None:
    install_root.mkdir(parents=True, exist_ok=True)
    for name in ("orchestrator", "scripts"):
        source = source_root / name
        if not source.exists():
            raise FileNotFoundError(source)
        destination = install_root / name
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def install(
    *,
    source_root: Path,
    install_root: Path,
    mode: str,
    endpoint: str,
    worker_id: str,
    controller_version: str,
    dispatch_priority: int,
    port: int,
    startup_root: Path | None = None,
) -> dict:
    if mode not in {"control-plane-worker", "worker"}:
        raise ValueError("mode must be control-plane-worker or worker")
    copy_runtime(source_root, install_root)

    data_dir = install_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    worker_config = {
        "endpoint": endpoint,
        "worker_id": worker_id,
        "roles": ["builder", "ci-remediator", "e2e-validator"],
        "controller_version": controller_version,
        "dispatch_priority": dispatch_priority,
        "heartbeat_ttl_seconds": 120,
        "heartbeat_interval_seconds": 20,
        "poll_interval_seconds": 2,
        "lease_seconds": 180,
    }
    worker_path = install_root / "worker-config.json"
    worker_path.write_text(
        json.dumps(worker_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    supervisor = {
        "mode": mode,
        "install_root": str(install_root),
        "worker_config": str(worker_path),
        "restart_delay_seconds": 5,
    }
    if mode == "control-plane-worker":
        supervisor.update(
            {
                "host": "0.0.0.0",
                "port": port,
                "db_path": str(data_dir / "orchestrator.db"),
                "backup_path": str(data_dir / "orchestrator.backup.db"),
                "backup_interval_seconds": 60,
                "ready_url": f"http://127.0.0.1:{port}/readyz",
            }
        )

    supervisor_path = install_root / "service-config.json"
    supervisor_path.write_text(
        json.dumps(supervisor, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    target_startup = startup_root or startup_dir()
    target_startup.mkdir(parents=True, exist_ok=True)
    startup_path = target_startup / f"ReqSys-Orchestrator-{worker_id}.cmd"
    python_exe = Path(sys.executable)
    startup_path.write_text(
        "@echo off\n"
        "setlocal\n"
        f'cd /d "{install_root}"\n'
        ":restart\n"
        f'"{python_exe}" -m scripts.service_supervisor --config "{supervisor_path}"\n'
        "timeout /t 5 /nobreak >nul\n"
        "goto restart\n",
        encoding="utf-8",
    )
    return {
        "install_root": str(install_root),
        "startup_path": str(startup_path),
        "supervisor_config": str(supervisor_path),
        "worker_config": str(worker_path),
        "mode": mode,
    }


def start_supervisor(install_root: Path, supervisor_path: Path) -> int:
    logs = install_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / "supervisor.log"
    log_handle = log_path.open("ab", buffering=0)
    kwargs = {
        "cwd": str(install_root),
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scripts.service_supervisor",
            "--config",
            str(supervisor_path),
        ],
        **kwargs,
    )
    (install_root / "supervisor.pid").write_text(
        str(process.pid) + "\n", encoding="utf-8"
    )
    return process.pid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--install-root", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--controller-version", required=True)
    parser.add_argument("--dispatch-priority", type=int, default=100)
    parser.add_argument("--port", type=int, default=18787)
    parser.add_argument("--startup-root")
    parser.add_argument("--start-now", action="store_true")
    args = parser.parse_args()

    result = install(
        source_root=Path(args.source_root),
        install_root=Path(args.install_root),
        mode=args.mode,
        endpoint=args.endpoint,
        worker_id=args.worker_id,
        controller_version=args.controller_version,
        dispatch_priority=args.dispatch_priority,
        port=args.port,
        startup_root=Path(args.startup_root) if args.startup_root else None,
    )
    if args.start_now:
        result["supervisor_pid"] = start_supervisor(
            Path(result["install_root"]),
            Path(result["supervisor_config"]),
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
