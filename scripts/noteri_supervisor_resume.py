"""Retomada governada do supervisor Noteri: identidade real, sem matar PID antigo."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import json
import ntpath
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen

ROOT = Path(r"C:\dev\chatgpt-workers\reqsys-orchestrator-24x7-runtime")
PYTHON = ROOT / "maintenance/python-3.12.10-embed-amd64/python.exe"
TOOLS = ROOT / "maintenance/process-inspection-7.2.2"
WHEEL_URL = "https://files.pythonhosted.org/packages/b4/90/e2159492b5426be0c1fef7acba807a03511f97c5f86b3caeda6ad92351a7/psutil-7.2.2-cp37-abi3-win_amd64.whl"
WHEEL_SHA = "eb7e81434c8d223ec4a219b5fc1c47d0417b12be7ea866e24fb5ad6e84b3d988"
RUNTIME_SHA = "63d26ff024e9f782bdddb7e954a6e247c8ef13b7"
EXPECTED = {
    "scripts/service_supervisor.py": "95f2760e100afb34f9510c8001fc390a1f164093d115828118956bde5ae3a6a7",
    "orchestrator/worker_agent.py": "76120670af59dedf27e6976ccb7426fa33efdbef1b2875c2abfafe538d8af6aa",
    "service-config.json": "9744d50b394fa72ad553ad299521d3dadb1789ece779f6c499313b3fdb0f2aa5",
    "worker-config.json": "f54d20cbf780902426dd400517d7776fb78b2ce0acdbd8623a954224bbc71445",
    "runtime-version.json": "ab94cbf9155ad133ae9fcd00315fa7a60747e3dadc80ce84386e4d91605dd017",
}
CONTROL = "http://DESKTOP-PDQK954:8787"
CONFIRM = "START-EXISTING-NOTERI-SUPERVISOR-DEV"


class Blocked(RuntimeError):
    pass


def norm(value):
    return ntpath.normcase(ntpath.normpath(str(value)))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def plain(path):
    for p in (path, *path.parents):
        if p.is_symlink() or (p.exists() and getattr(p.lstat(), "st_file_attributes", 0) & 1024):
            raise Blocked("link_rejected")


def read(path, limit=1024*1024):
    plain(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise Blocked("file_missing_or_oversized")
    data = path.read_bytes()
    if len(data) > limit:
        raise Blocked("file_oversized")
    return data


def load(path):
    value = json.loads(read(path).decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise Blocked("json_object_required")
    return value


def wheel_entries(raw):
    if len(raw) > 2*1024*1024 or sha(raw) != WHEEL_SHA:
        raise Blocked("process_library_digest_mismatch")
    result = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for entry in z.infolist():
            p = PurePosixPath(entry.filename)
            if p.is_absolute() or ".." in p.parts or "\\" in entry.filename or ":" in entry.filename:
                raise Blocked("wheel_path_rejected")
            if entry.is_dir():
                continue
            if entry.filename.casefold() in {x.casefold() for x in result}:
                raise Blocked("wheel_duplicate")
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise Blocked("wheel_link")
            if entry.file_size > 2*1024*1024:
                raise Blocked("wheel_size")
            result[entry.filename] = z.read(entry)
    if len(result) > 100 or sum(map(len, result.values())) > 4*1024*1024:
        raise Blocked("wheel_expansion")
    return result


def verify_tools():
    raw = read(TOOLS / "distribution.whl", 2*1024*1024)
    entries = wheel_entries(raw)
    actual = {p.relative_to(TOOLS).as_posix() for p in TOOLS.rglob("*") if p.is_file()}
    if actual != set(entries) | {"distribution.whl"}:
        raise Blocked("process_library_file_set_changed")
    for name, data in entries.items():
        if read(TOOLS / name, 2*1024*1024) != data:
            raise Blocked("process_library_file_changed")


def prepare_tools():
    plain(TOOLS)
    if TOOLS.exists():
        verify_tools()
        return {"state": "already_prepared"}
    TOOLS.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(WHEEL_URL, timeout=20) as response:
        if response.status != 200 or response.geturl() != WHEEL_URL:
            raise Blocked("process_library_source_invalid")
        raw = response.read(2*1024*1024+1)
    entries = wheel_entries(raw)
    with tempfile.TemporaryDirectory(prefix="process-probe-", dir=TOOLS.parent) as temp:
        stage = Path(temp)
        for name, data in entries.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (stage / "distribution.whl").write_bytes(raw)
        if TOOLS.exists():
            raise Blocked("concurrent_dependency_preparation")
        os.rename(stage, TOOLS)
    verify_tools()
    return {"state": "prepared", "wheel_sha256": WHEEL_SHA}


def library():
    verify_tools()
    sys.path.insert(0, str(TOOLS))
    ps = importlib.import_module("psutil")
    if ps.__version__ != "7.2.2" or Path(ps.__file__).resolve().parent != (TOOLS / "psutil").resolve():
        raise Blocked("process_library_identity")
    return ps


def role(row):
    args = row.get("cmdline") or []
    for module, name, cfg in (
        ("scripts.service_supervisor", "supervisor", ROOT / "service-config.json"),
        ("orchestrator.worker_agent", "worker", ROOT / "worker-config.json"),
    ):
        if module not in args:
            continue
        target = norm(cfg) in [norm(a) for a in args]
        if not target and norm(row.get("cwd") or "") != norm(ROOT):
            continue
        expected = [str(PYTHON), "-m", module, "--config", str(cfg)]
        filtered = [a for a in args if a != "-B"]
        if ([norm(a) for a in filtered] != [norm(a) for a in expected]
                or norm(row.get("exe") or "") != norm(PYTHON)
                or norm(row.get("cwd") or "") != norm(ROOT)):
            raise Blocked("runtime_process_identity_mismatch")
        return name
    return None


def collect_processes(ps):
    result, inaccessible = [], 0
    for proc in ps.process_iter(["pid", "name"]):
        if not str(proc.info.get("name") or "").casefold().startswith(("python", "pypy")):
            continue
        try:
            row = {"pid": proc.pid, "exe": proc.exe(), "cmdline": proc.cmdline(),
                   "cwd": proc.cwd(), "create_time": proc.create_time(), "ppid": proc.ppid()}
            label = role(row)
            if label:
                result.append({"role": label, "pid": row["pid"], "ppid": row["ppid"],
                               "created_at": row["create_time"]})
        except ps.NoSuchProcess:
            continue
        except ps.AccessDenied:
            inaccessible += 1
    return {"processes": result, "unreadable_python_processes": inaccessible}


def decision(snapshot):
    if snapshot["unreadable_python_processes"]:
        raise Blocked("python_process_identity_unreadable")
    sups = [p for p in snapshot["processes"] if p["role"] == "supervisor"]
    workers = [p for p in snapshot["processes"] if p["role"] == "worker"]
    if len(sups) > 1 or len(workers) > 1:
        raise Blocked("multiple_runtime_processes")
    if workers and (not sups or workers[0]["ppid"] != sups[0]["pid"]):
        raise Blocked("worker_parent_identity_mismatch")
    return "existing" if sups else "absent"


def validate_installation():
    from scripts import noteri_supervisor_python_repair as repair
    for rel, expected in EXPECTED.items():
        if sha(read(ROOT / rel)) != expected:
            raise Blocked("installed_file_changed:" + rel)
    repair.validate_python(PYTHON.parent)
    cfg = load(ROOT / "service-config.json")
    if cfg.get("mode") != "worker" or norm(cfg.get("install_root")) != norm(ROOT):
        raise Blocked("runtime_config_identity")
    if norm(cfg.get("worker_config")) != norm(ROOT / "worker-config.json"):
        raise Blocked("worker_config_identity")
    profile = Path(os.environ["LOCALAPPDATA"]) / "ReqSys/TodoGlobal24x7/host-profile.json"
    before = read(profile)
    if load(profile).get("profile") not in {"NORMAL", "ESTUDO"}:
        raise Blocked("profile_invalid")
    return profile, before


def registry():
    request = Request(CONTROL + "/v1/workers", headers={"Accept": "application/json", "Cache-Control": "no-store"})
    with urlopen(request, timeout=5) as response:
        data = json.loads(response.read(512*1024))
    workers = data.get("workers") if isinstance(data, dict) else None
    if not isinstance(workers, list):
        raise Blocked("registry_invalid")
    matches = [w for w in workers if w.get("worker_id") == "noteri" and str(w.get("device_name")).casefold() == "noteri"]
    if len(matches) != 1:
        raise Blocked("registry_identity_not_unique")
    w = matches[0]
    caps = w.get("capabilities") or {}
    return {"fresh": w.get("fresh") is True, "controller_online": w.get("controller_online") is True,
            "auth_valid": w.get("auth_valid") is True, "profile": w.get("profile"),
            "last_heartbeat": w.get("last_heartbeat"),
            "profile_capable": "host.profile.set.v1" in caps.get("safe_task_types", [])}


@contextmanager
def exclusive():
    import msvcrt
    path = ROOT / "maintenance/supervisor-resume.lock"
    plain(path)
    with path.open("a+b") as f:
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise Blocked("supervisor_resume_locked") from exc
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def resume(ps, correlation):
    with exclusive():
        profile, original_profile = validate_installation()
        before = collect_processes(ps)
        state = decision(before)
        remote = registry()
        if state == "existing":
            return {"state": "already_running", "before": before, "registry": remote,
                    "process_started": False, "profile_changed": False}
        if remote["fresh"]:
            raise Blocked("fresh_worker_without_matching_process")
        for name in ("shutdown.request", "restart-worker.request", "refresh-runtime.request.json"):
            if (ROOT / "data/control" / name).exists():
                raise Blocked("pending_control_request")
        if decision(collect_processes(ps)) != "absent":
            raise Blocked("concurrent_runtime_start")
        log = ROOT / "logs" / ("supervisor-resume-" + correlation + ".log")
        plain(log)
        log.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.pop("RUNNER_TRACKING_ID", None)
        started = time.time()
        with log.open("ab", buffering=0) as out:
            child = subprocess.Popen(
                [str(PYTHON), "-B", "-m", "scripts.service_supervisor", "--config", str(ROOT / "service-config.json")],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
        try:
            # Não reutilizar PIDs históricos nem chamar o reinício legado.
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise Blocked("created_supervisor_exited")
                status = load(ROOT / "runtime-status.json")
                if status.get("supervisor_pid") == child.pid and status.get("updated_at_epoch", 0) >= started:
                    observed = collect_processes(ps)
                    decision(observed)
                    if len(observed["processes"]) == 2:
                        if read(profile) != original_profile:
                            raise Blocked("profile_changed_concurrently")
                        pidfile = ROOT / "supervisor.pid"
                        old = read(pidfile) if pidfile.exists() else b""
                        record = ROOT / "maintenance" / ("resume-" + correlation + ".json")
                        payload = {"state": "started", "process_started": True, "processes": observed["processes"],
                                   "previous_pid_file": old.decode("ascii", errors="replace").strip(),
                                   "runtime_sha": RUNTIME_SHA, "profile_changed": False,
                                   "registry_before": remote}
                        from scripts.noteri_supervisor_python_repair import atomic_write
                        atomic_write(record, (json.dumps(payload, sort_keys=True) + "\n").encode())
                        atomic_write(pidfile, (str(child.pid) + "\n").encode())
                        return payload
                time.sleep(1)
            raise Blocked("created_supervisor_not_validated")
        except BaseException:
            # Reversão somente da instância criada nesta chamada, por sua API de controle.
            current = collect_processes(ps)
            sups = [p for p in current["processes"] if p["role"] == "supervisor"]
            if decision(current) == "existing" and len(sups) == 1 and sups[0]["pid"] == child.pid:
                stop = ROOT / "data/control/shutdown.request"
                plain(stop)
                with stop.open("xb") as f:
                    f.write(b"rollback-of-owned-start\n")
                try:
                    child.wait(timeout=12)
                except subprocess.TimeoutExpired as exc:
                    raise Blocked("owned_start_rollback_not_confirmed") from exc
            raise


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["prepare-tools", "inspect", "start"])
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--correlation-id", required=True)
    p.add_argument("--confirm")
    a = p.parse_args()
    try:
        if os.name != "nt" or socket.gethostname().casefold() != "noteri":
            raise Blocked("host_not_authorized")
        if not re.fullmatch("[0-9a-f]{40}", a.expected_sha) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,100}", a.correlation_id):
            raise Blocked("identity_invalid")
        repo = Path(__file__).resolve().parents[1]
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, text=True, capture_output=True, timeout=10)
        if head.returncode or head.stdout.strip() != a.expected_sha:
            raise Blocked("source_sha_mismatch")
        if a.action == "prepare-tools":
            result = prepare_tools()
        else:
            ps = library()
            if a.action == "inspect":
                result = collect_processes(ps)
                result.update({"decision": decision(result), "registry": registry(), "process_started": False})
            else:
                if a.confirm != CONFIRM:
                    raise Blocked("start_not_confirmed")
                result = resume(ps, a.correlation_id)
        result.update({"host": "Noteri", "environment": "dev", "source_sha": a.expected_sha,
                       "correlation_id": a.correlation_id, "reboot": False, "other_processes_stopped": False})
        print(json.dumps(result, sort_keys=True))
        return 0
    except (Blocked, OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        reason = str(exc) if isinstance(exc, Blocked) else type(exc).__name__
        print(json.dumps({"ok": False, "reason": reason, "correlation_id": a.correlation_id}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
