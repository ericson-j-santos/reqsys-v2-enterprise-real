"""E2E de reinicio supervisionado do worker Noteri; nao derruba supervisor nem host."""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path

CONFIRM = "VALIDATE-NOTERI-WORKER-RESTART-DEV"


class Blocked(RuntimeError):
    pass


def pair(snapshot, *, worker_required=True):
    if snapshot.get("unreadable_python_processes") != 0:
        raise Blocked("process_identity_unreadable")
    processes = snapshot.get("processes")
    if not isinstance(processes, list):
        raise Blocked("process_snapshot_invalid")
    supervisors = [p for p in processes if p.get("role") == "supervisor"]
    workers = [p for p in processes if p.get("role") == "worker"]
    if len(supervisors) != 1 or len(workers) > 1 or len(processes) != len(supervisors)+len(workers):
        raise Blocked("process_identity_not_unique")
    if worker_required and len(workers) != 1:
        raise Blocked("worker_missing")
    supervisor, worker = supervisors[0], workers[0] if workers else None
    for item in (supervisor, worker):
        if item is not None and (type(item.get("pid")) is not int or item["pid"] <= 0
                                 or not isinstance(item.get("created_at"), (int, float))):
            raise Blocked("process_identity_invalid")
    if worker is not None and worker.get("ppid") != supervisor["pid"]:
        raise Blocked("worker_parent_mismatch")
    return supervisor, worker


def replaced(before, after):
    old_supervisor, old_worker = pair(before)
    supervisor, worker = pair(after, worker_required=False)
    if supervisor != old_supervisor:
        raise Blocked("supervisor_changed_during_test")
    return worker is not None and (
        worker["pid"], worker["created_at"]) != (
        old_worker["pid"], old_worker["created_at"])


def require_study(registry, local_profile):
    if local_profile != "ESTUDO" or registry.get("profile") != "ESTUDO":
        raise Blocked("study_precondition_required")
    if any(registry.get(key) is not True for key in (
            "fresh", "controller_online", "auth_valid", "profile_capable")):
        raise Blocked("worker_not_ready_for_recovery_test")


def validate_identity(expected_sha, correlation_id, confirm, *, host=None, platform=None):
    if (platform or os.name) != "nt" or (host or socket.gethostname()).casefold() != "noteri":
        raise Blocked("host_not_authorized")
    if confirm != CONFIRM:
        raise Blocked("recovery_test_not_confirmed")
    if not re.fullmatch("[0-9a-f]{40}", expected_sha) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{7,90}", correlation_id):
        raise Blocked("source_or_correlation_invalid")


def execute(expected_sha, correlation_id, confirm):
    validate_identity(expected_sha, correlation_id, confirm)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
                          capture_output=True, text=True, timeout=10, check=False)
    if head.returncode or head.stdout.strip() != expected_sha:
        raise Blocked("source_sha_mismatch")
    from scripts import noteri_supervisor_resume as proc
    from scripts.noteri_supervisor_python_repair import atomic_write
    from scripts import noteri_worker_heartbeat_probe as heartbeat

    with proc.exclusive():
        profile, original_profile = proc.validate_installation()
        ps = proc.library()
        before = proc.collect_processes(ps)
        supervisor, worker = pair(before)
        registry = proc.registry()
        require_study(registry, proc.load(profile).get("profile"))
        record = proc.ROOT / "maintenance" / ("recovery-test-" + correlation_id + ".json")
        proc.plain(record)
        if record.exists():
            previous = proc.load(record)
            if previous.get("state") != "validated" or previous.get("source_sha") != expected_sha:
                raise Blocked("existing_recovery_test_requires_reconciliation")
            if previous.get("supervisor") != supervisor:
                raise Blocked("replay_supervisor_identity_changed")
            return {**previous, "state": "already_validated", "new_restart_requested": False}
        control = proc.ROOT / "data/control"
        for name in ("shutdown.request", "restart-worker.request",
                     "restart-server.request", "refresh-runtime.request.json"):
            proc.plain(control / name)
            if (control / name).exists():
                raise Blocked("existing_control_request")
        if proc.collect_processes(ps) != before:
            raise Blocked("concurrent_process_change")
        request_path = control / "restart-worker.request"
        started = time.time()
        receipt = {"state": "requested", "source_sha": expected_sha,
                   "correlation_id": correlation_id, "supervisor": supervisor,
                   "old_worker": worker, "requested_at_epoch": started}
        atomic_write(record, (json.dumps(receipt, sort_keys=True)+"\n").encode())
        with request_path.open("xb") as output:
            output.write((correlation_id+"\n").encode())
            output.flush()
            os.fsync(output.fileno())
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            after = proc.collect_processes(ps)
            if replaced(before, after):
                status = proc.load(proc.ROOT / "runtime-status.json")
                new_supervisor, new_worker = pair(after)
                if (not request_path.exists() and status.get("worker_pid") == new_worker["pid"]
                        and status.get("supervisor_pid") == supervisor["pid"]
                        and status.get("updated_at_epoch", 0) >= started):
                    break
            time.sleep(1)
        else:
            raise Blocked("supervised_restart_not_confirmed")
        proof = heartbeat.check(expected_sha=expected_sha, correlation_id=correlation_id)
        final = proc.collect_processes(ps)
        if final != after:
            raise Blocked("processes_changed_during_heartbeat_proof")
        require_study(proc.registry(), proc.load(profile).get("profile"))
        if proc.read(profile) != original_profile:
            raise Blocked("profile_changed_during_recovery_test")
        for rel, expected in proc.EXPECTED.items():
            if proc.sha(proc.read(proc.ROOT / rel)) != expected:
                raise Blocked("installed_configuration_changed")
        receipt.update({"state": "validated", "new_restart_requested": True,
                        "worker": new_worker, "profile": "ESTUDO", "profile_changed": False,
                        "heartbeat_advanced": proof["heartbeat_advanced"],
                        "first_heartbeat": proof["first_heartbeat"],
                        "second_heartbeat": proof["second_heartbeat"],
                        "request_consumed": True, "supervisor_unchanged": True,
                        "method": "existing_supervisor_control_request",
                        "unexpected_crash_tested": False, "supervisor_crash_tested": False,
                        "host_reboot_tested": False, "runtime_sha": proc.RUNTIME_SHA})
        atomic_write(record, (json.dumps(receipt, sort_keys=True)+"\n").encode())
        return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        result = execute(args.expected_sha, args.correlation_id, args.confirm)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        message = str(error)
        reason = message if re.fullmatch("[a-z][a-z0-9_]{0,100}", message) else type(error).__name__
        print(json.dumps({"ok": False, "reason": reason, "correlation_id": args.correlation_id}))
        return 2
    print(json.dumps({"ok": True, "host": "Noteri", "environment": "dev", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
