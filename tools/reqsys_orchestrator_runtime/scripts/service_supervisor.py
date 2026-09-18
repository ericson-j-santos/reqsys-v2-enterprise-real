from __future__ import annotations

import argparse
import json
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


def start_server(config: dict) -> subprocess.Popen:
    return subprocess.Popen(
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


def start_worker(config: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "orchestrator.worker_agent",
            "--config",
            config["worker_config"],
        ],
        cwd=config["install_root"],
    )


def stop_child(child: subprocess.Popen | None) -> None:
    if child is None or child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def supervise(config: dict) -> None:
    mode = config["mode"]
    if mode not in {"control-plane-worker", "worker"}:
        raise ValueError("unsupported supervisor mode")

    restart_delay = float(config.get("restart_delay_seconds", 5))
    backup_interval = float(config.get("backup_interval_seconds", 60))
    server: subprocess.Popen | None = None
    worker: subprocess.Popen | None = None
    last_backup = 0.0

    try:
        while True:
            if mode == "control-plane-worker":
                restore_if_missing(config["db_path"], config["backup_path"])
                if server is None or server.poll() is not None:
                    server = start_server(config)
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        if server.poll() is not None:
                            break
                        if ready(config["ready_url"]):
                            break
                        time.sleep(0.5)
                    if not ready(config["ready_url"]):
                        stop_child(server)
                        server = None
                        time.sleep(restart_delay)
                        continue

                now = time.monotonic()
                if now - last_backup >= backup_interval and Path(config["db_path"]).exists():
                    backup_database(config["db_path"], config["backup_path"])
                    last_backup = now

            if worker is None or worker.poll() is not None:
                worker = start_worker(config)
                time.sleep(0.5)
                if worker.poll() is not None:
                    worker = None
                    time.sleep(restart_delay)
                    continue

            time.sleep(1)
    except KeyboardInterrupt:
        return
    finally:
        stop_child(worker)
        stop_child(server)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    supervise(config)


if __name__ == "__main__":
    main()
