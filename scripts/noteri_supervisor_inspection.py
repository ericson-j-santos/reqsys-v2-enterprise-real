"""Read-only, allowlisted Noteri supervisor installation inspection."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
import time
from pathlib import Path

RUNTIME = Path(r"C:\dev\chatgpt-workers\reqsys-orchestrator-24x7-runtime")
LIMIT = 131072
SHA_RE = re.compile(r"[0-9a-f]{40}")
CID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}")


def read_fixed(path: Path) -> tuple[dict, bytes | None]:
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or getattr(parent.lstat(), "st_file_attributes", 0) & 1024):
            return {"state": "link_rejected"}, None
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
            return {"state": "type_or_size_rejected"}, None
        data = path.read_bytes()
        if len(data) > LIMIT:
            return {"state": "type_or_size_rejected"}, None
        return {"state": "read", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}, data
    except FileNotFoundError:
        return {"state": "missing"}, None
    except OSError:
        return {"state": "unreadable"}, None


def read_object(path: Path) -> tuple[dict, dict]:
    meta, data = read_fixed(path)
    if data is None:
        return meta, {}
    try:
        obj = json.loads(data.decode("utf-8-sig"))
        if not isinstance(obj, dict):
            raise ValueError("not_object")
    except (UnicodeError, ValueError):
        return {**meta, "json_valid": False}, {}
    return {**meta, "json_valid": True}, obj


def safe_number(obj: dict, key: str) -> int | float | None:
    value = obj.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value < 10**13:
        return value
    return None


def inspect_layout(runtime: Path, appdata: Path, local: Path, now: float) -> dict:
    wm, worker = read_object(runtime / "worker-config.json")
    sm, supervisor = read_object(runtime / "service-config.json")
    rm, status = read_object(runtime / "runtime-status.json")
    vm, version = read_object(runtime / "runtime-version.json")
    profile = local / "ReqSys" / "TodoGlobal24x7" / "host-profile.json"
    pm, profile_obj = read_object(profile)
    wrapper = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "ReqSys-Orchestrator-noteri.cmd"
    bm, wrapper_bytes = read_fixed(wrapper)
    wrapper_text = wrapper_bytes.decode("utf-8", errors="replace") if wrapper_bytes else ""
    interpreters = re.findall(r'(?im)^\s*"([^"\r\n]+python(?:w)?\.exe)"\s+-m\s+scripts\.service_supervisor\b', wrapper_text)
    executable = Path(interpreters[0]) if len(set(interpreters)) == 1 else None
    try:
        interpreter_state = ("present" if executable.is_file() else "missing") if executable else "unresolved"
    except OSError:
        interpreter_state = "unreadable"
    age = safe_number(status, "updated_at_epoch")
    version_sha = str(version.get("source_sha") or "")
    safe_version = version_sha if SHA_RE.fullmatch(version_sha) else None
    files = {}
    for rel in ("orchestrator/worker_agent.py", "scripts/service_supervisor.py", "supervisor.pid",
                "bootstrap/runtime_bootstrap_shim.py", "bootstrap/bootstrap-config.json"):
        meta, _ = read_fixed(runtime / rel)
        files[rel] = meta
    return {
        "runtime_exists": runtime.is_dir(),
        "worker_config": {
            **wm,
            "worker_id_expected": worker.get("worker_id") == "noteri",
            "endpoint_expected": str(worker.get("endpoint") or "").rstrip("/") == "http://DESKTOP-PDQK954:8787",
            "heartbeat_interval_seconds": safe_number(worker, "heartbeat_interval_seconds"),
            "heartbeat_ttl_seconds": safe_number(worker, "heartbeat_ttl_seconds"),
            "profile_path_configured": bool(worker.get("profile_path")),
        },
        "supervisor_config": {
            **sm, "mode_worker": supervisor.get("mode") == "worker",
            "install_root_expected": str(supervisor.get("install_root") or "").replace("\\", "/").casefold() == str(runtime).replace("\\", "/").casefold(),
            "worker_config_expected": str(supervisor.get("worker_config") or "").replace("\\", "/").casefold() == str(runtime / "worker-config.json").replace("\\", "/").casefold(),
        },
        "runtime_status": {
            **rm, "age_seconds": round(max(0, now - age), 1) if age is not None else None,
            "supervisor_pid_recorded": safe_number(status, "supervisor_pid"),
            "worker_pid_recorded": safe_number(status, "worker_pid"),
            "worker_restarts": safe_number(status, "worker_restarts"),
            "pid_liveness_verified": False,
        },
        "runtime_version": {**vm, "source_sha": safe_version},
        "startup": {**bm, "supervisor_command_count": len(interpreters),
                    "interpreter_file_state": interpreter_state,
                    "interpreter_path": str(executable) if executable else None},
        "profile": {**pm, "profile": profile_obj.get("profile") if profile_obj.get("profile") in ("NORMAL", "ESTUDO") else None},
        "files": files,
    }


def collect(expected_sha: str, correlation_id: str) -> dict:
    if os.name != "nt" or socket.gethostname().casefold() != "noteri":
        raise ValueError("host_not_authorized")
    if not SHA_RE.fullmatch(expected_sha) or not CID_RE.fullmatch(correlation_id):
        raise ValueError("source_or_correlation_invalid")
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                            text=True, capture_output=True, timeout=10, check=False)
    if result.returncode or result.stdout.strip() != expected_sha:
        raise ValueError("source_sha_mismatch")
    appdata, local = os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA")
    if not appdata or not local:
        raise ValueError("host_directory_context_missing")
    return {"inspection_ok": True, "read_only": True, "host": "Noteri", "environment": "dev",
            "source_sha": expected_sha, "correlation_id": correlation_id,
            "layout": inspect_layout(RUNTIME, Path(appdata), Path(local), time.time())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args()
    try:
        report = collect(args.expected_sha, args.correlation_id)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        code = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(json.dumps({"inspection_ok": False, "reason": code}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
