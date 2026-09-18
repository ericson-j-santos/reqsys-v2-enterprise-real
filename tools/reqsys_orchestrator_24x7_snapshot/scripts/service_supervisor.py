from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from orchestrator.persistence import backup_database, restore_if_missing


def ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=3) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def event(name: str, **fields) -> None:
    print(json.dumps({"event": name, **fields}, sort_keys=True), flush=True)


def start_server(config: dict) -> subprocess.Popen:
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "orchestrator",
            "serve",
            "--host",
            config["host"],
            "--port",
            str(config["port"]),
            "--db-path",
            config["db_path"],
        ],
        cwd=config["install_root"],
    )
    event("server_started", pid=child.pid)
    return child


def start_worker(config: dict) -> subprocess.Popen:
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "orchestrator.worker_agent",
            "--config",
            config["worker_config"],
        ],
        cwd=config["install_root"],
    )
    event("worker_started", pid=child.pid)
    return child


def stop_child(child: subprocess.Popen | None) -> None:
    if child is None or child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def consume_request(control_dir: Path, name: str) -> bool:
    path = control_dir / name
    if not path.exists():
        return False
    path.unlink()
    return True


def write_status(
    path: Path,
    *,
    mode: str,
    server: subprocess.Popen | None,
    worker: subprocess.Popen | None,
    server_restarts: int,
    worker_restarts: int,
    ready_state: bool,
    last_backup_at: float | None,
) -> None:
    atomic_json(
        path,
        {
            "supervisor_pid": os.getpid(),
            "mode": mode,
            "server_pid": server.pid if server and server.poll() is None else None,
            "worker_pid": worker.pid if worker and worker.poll() is None else None,
            "server_restarts": server_restarts,
            "worker_restarts": worker_restarts,
            "ready": ready_state,
            "last_backup_at_epoch": last_backup_at,
            "updated_at_epoch": time.time(),
        },
    )


def supervise(config: dict) -> None:
    mode = config["mode"]
    if mode not in {"control-plane-worker", "worker"}:
        raise ValueError("unsupported supervisor mode")

    install_root = Path(config["install_root"])
    control_dir = install_root / "data" / "control"
    status_path = install_root / "runtime-status.json"
    control_dir.mkdir(parents=True, exist_ok=True)

    restart_delay = float(config.get("restart_delay_seconds", 5))
    backup_interval = float(config.get("backup_interval_seconds", 60))
    server: subprocess.Popen | None = None
    worker: subprocess.Popen | None = None
    last_backup_monotonic = 0.0
    last_backup_epoch: float | None = None
    server_starts = 0
    worker_starts = 0

    try:
        while True:
            if consume_request(control_dir, "shutdown.request"):
                event("shutdown_requested")
                return
            if consume_request(control_dir, "restart-server.request"):
                event("server_restart_requested")
                stop_child(server)
                server = None
            if consume_request(control_dir, "restart-worker.request"):
                event("worker_restart_requested")
                stop_child(worker)
                worker = None

            ready_state = False
            if mode == "control-plane-worker":
                restore_if_missing(config["db_path"], config["backup_path"])
                if server is None or server.poll() is not None:
                    server = start_server(config)
                    server_starts += 1
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        if server.poll() is not None:
                            break
                        if ready(config["ready_url"]):
                            break
                        time.sleep(0.5)
                    if not ready(config["ready_url"]):
                        event("server_not_ready", pid=server.pid if server else None)
                        stop_child(server)
                        server = None
                        write_status(
                            status_path,
                            mode=mode,
                            server=server,
                            worker=worker,
                            server_restarts=max(0, server_starts - 1),
                            worker_restarts=max(0, worker_starts - 1),
                            ready_state=False,
                            last_backup_at=last_backup_epoch,
                        )
                        time.sleep(restart_delay)
                        continue
                ready_state = ready(config["ready_url"])

                now = time.monotonic()
                if (
                    now - last_backup_monotonic >= backup_interval
                    and Path(config["db_path"]).exists()
                ):
                    backup_database(config["db_path"], config["backup_path"])
                    last_backup_monotonic = now
                    last_backup_epoch = time.time()
                    event("backup_completed", path=config["backup_path"])

            if worker is None or worker.poll() is not None:
                worker = start_worker(config)
                worker_starts += 1
                time.sleep(0.5)
                if worker.poll() is not None:
                    event("worker_start_failed")
                    worker = None
                    write_status(
                        status_path,
                        mode=mode,
                        server=server,
                        worker=worker,
                        server_restarts=max(0, server_starts - 1),
                        worker_restarts=max(0, worker_starts - 1),
                        ready_state=ready_state,
                        last_backup_at=last_backup_epoch,
                    )
                    time.sleep(restart_delay)
                    continue

            write_status(
                status_path,
                mode=mode,
                server=server,
                worker=worker,
                server_restarts=max(0, server_starts - 1),
                worker_restarts=max(0, worker_starts - 1),
                ready_state=ready_state if mode == "control-plane-worker" else True,
                last_backup_at=last_backup_epoch,
            )
            time.sleep(1)
    except KeyboardInterrupt:
        return
    finally:
        stop_child(worker)
        stop_child(server)
        write_status(
            status_path,
            mode=mode,
            server=None,
            worker=None,
            server_restarts=max(0, server_starts - 1),
            worker_restarts=max(0, worker_starts - 1),
            ready_state=False,
            last_backup_at=last_backup_epoch,
        )
        event("supervisor_stopped")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    supervise(config)


if __name__ == "__main__":
    main()
