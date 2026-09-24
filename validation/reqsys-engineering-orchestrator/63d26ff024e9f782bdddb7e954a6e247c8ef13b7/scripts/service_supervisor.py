from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from urllib.error import URLError
from urllib.request import urlopen

from orchestrator.persistence import backup_database, restore_if_missing


RUNTIME_REFRESH_REQUEST = "refresh-runtime.request.json"
RUNTIME_REFRESH_TTL_SECONDS = 900
RUNTIME_REFRESH_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
APPROVED_ORIGIN = "https://github.com/ericson-j-santos/reqsys-engineering-orchestrator"


def normalize_origin_url(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("git@github.com:"):
        text = "https://github.com/" + text[len("git@github.com:"):]
    elif text.startswith("ssh://git@github.com/"):
        text = "https://github.com/" + text[len("ssh://git@github.com/"):]
    if text.endswith(".git"):
        text = text[:-4]
    return text.rstrip("/").casefold()


def git_text(source_root: Path, *args: str, timeout: int = 60) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed with exit={completed.returncode}")
    return completed.stdout.strip()


def git_bytes(source_root: Path, *args: str, timeout: int = 60) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(source_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed with exit={completed.returncode}")
    return bytes(completed.stdout)


def load_runtime_refresh_request(path: Path, now: float | None = None) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise ValueError("unsupported runtime refresh request version")
    host = str(payload.get("target_host") or "")
    if host.casefold() != socket.gethostname().casefold():
        raise ValueError("runtime refresh request belongs to another host")
    expected = str(payload.get("expected_sha") or "").lower()
    if not RUNTIME_REFRESH_SHA_RE.fullmatch(expected):
        raise ValueError("invalid runtime refresh expected_sha")
    requested = float(payload.get("requested_at_epoch"))
    not_before = float(payload.get("not_before_epoch"))
    reference = time.time() if now is None else now
    if requested > reference + 60:
        raise ValueError("runtime refresh request is from the future")
    if reference - requested > RUNTIME_REFRESH_TTL_SECONDS:
        raise ValueError("runtime refresh request expired")
    if not_before < requested or not_before - requested > 60:
        raise ValueError("runtime refresh not_before is invalid")
    payload["expected_sha"] = expected
    return payload


def _safe_extract_runtime_archive(raw: bytes, stage_root: Path) -> None:
    allowed = {"orchestrator", "scripts"}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("unsafe runtime archive path")
            if path.parts[0] not in allowed:
                raise ValueError("runtime archive contains unexpected path")
        archive.extractall(stage_root)
    if not (stage_root / "orchestrator" / "__init__.py").is_file():
        raise ValueError("runtime archive missing orchestrator package")
    if not (stage_root / "scripts" / "service_supervisor.py").is_file():
        raise ValueError("runtime archive missing service supervisor")


def _install_staged_runtime(
    install_root: Path,
    stage_root: Path,
    expected_sha: str,
) -> dict:
    backup_root = install_root / "data" / "runtime-backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"{int(time.time())}-{expected_sha[:12]}"
    backup.mkdir(parents=True, exist_ok=False)
    for name in ("orchestrator", "scripts"):
        current = install_root / name
        staged = stage_root / name
        if not current.is_dir() or not staged.is_dir():
            raise ValueError(f"runtime directory missing: {name}")
        shutil.copytree(current, backup / name)
    try:
        for name in ("orchestrator", "scripts"):
            shutil.copytree(stage_root / name, install_root / name, dirs_exist_ok=True)
        atomic_json(
            install_root / "runtime-version.json",
            {
                "schema_version": 1,
                "source_sha": expected_sha,
                "updated_at_epoch": time.time(),
            },
        )
    except Exception:
        for name in ("orchestrator", "scripts"):
            shutil.copytree(backup / name, install_root / name, dirs_exist_ok=True)
        raise
    return {"backup": str(backup), "source_sha": expected_sha}


def apply_runtime_refresh(config: dict, install_root: Path, request: dict) -> dict:
    source_root_raw = str(config.get("source_root") or "").strip()
    if not source_root_raw:
        raise ValueError("source_root missing from supervisor config")
    source_root = Path(source_root_raw).resolve()
    if not source_root.is_dir():
        raise ValueError("source_root does not exist")

    origin = git_text(source_root, "remote", "get-url", "origin")
    if normalize_origin_url(origin) != APPROVED_ORIGIN.casefold():
        raise ValueError("source_root origin is not approved")

    expected = request["expected_sha"]
    git_text(source_root, "fetch", "--prune", "origin", "main", timeout=120)
    actual = git_text(source_root, "rev-parse", "origin/main").lower()
    if actual != expected:
        raise ValueError("origin/main does not match expected_sha")

    archive = git_bytes(
        source_root,
        "archive",
        "--format=zip",
        expected,
        "orchestrator",
        "scripts",
    )
    data_root = install_root / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="runtime-refresh-", dir=data_root) as tmp:
        stage_root = Path(tmp)
        _safe_extract_runtime_archive(archive, stage_root)
        result = _install_staged_runtime(install_root, stage_root, expected)
    result["origin"] = APPROVED_ORIGIN
    return result


def maybe_apply_runtime_refresh(config: dict, control_dir: Path, install_root: Path) -> bool:
    request_path = control_dir / RUNTIME_REFRESH_REQUEST
    if not request_path.is_file():
        return False
    try:
        request = load_runtime_refresh_request(request_path)
        if time.time() < float(request["not_before_epoch"]):
            return False
        result = apply_runtime_refresh(config, install_root, request)
        request_path.unlink(missing_ok=True)
        event(
            "runtime_refresh_applied",
            source_sha=result["source_sha"],
            backup=result["backup"],
            origin=result["origin"],
        )
        return True
    except Exception as exc:
        failed = control_dir / f"refresh-runtime.failed.{int(time.time())}.json"
        try:
            request_path.replace(failed)
        except OSError:
            request_path.unlink(missing_ok=True)
        event(
            "runtime_refresh_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:500],
        )
        return False


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
            if maybe_apply_runtime_refresh(config, control_dir, install_root):
                event("supervisor_restart_for_runtime_refresh")
                return
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
