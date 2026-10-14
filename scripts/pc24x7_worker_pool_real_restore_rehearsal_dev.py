#!/usr/bin/env python3
"""Governed DEV rehearsal: live SQLite online backup -> 1.4 -> 1.2 on an isolated volume.

The active coordinator, Docker Compose, its volume, port 8097 and real token
are never modified. Protected backups stay outside Git; plaintext is piped
only to an owned transient Docker volume and never enters artifacts or logs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent


def sibling(module: str, filename: str):
    path = HERE / filename
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("pinned_sibling_missing")
    spec = importlib.util.spec_from_file_location(module, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("pinned_sibling_unloadable")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


canary = sibling("workerpool_physical_candidate", "pc24x7_worker_pool_candidate_canary_dev.py")
backup = sibling("workerpool_physical_backup", "pc24x7_worker_pool_backup_restore_dev.py")
inventory = canary.inventory
HOST = inventory.HOST
WORKER_SHA = canary.WORKER_SHA
RULES_SHA = canary.RULES_SHA
CONFIRM = "RESTORE-WORKER-POOL-DEV-ISOLATED"
CORR = re.compile(r"pc24x7-workerpool-restore-[0-9]{6,18}-[1-9][0-9]?\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")
EVIDENCE = ROOT / "artifacts" / "pc24x7-worker-pool-real-restore-dev" / "evidence.json"

# Persisted business identity is compared, never published.
IDENTITY_SQL = """SELECT task_id,repository,issue_number,request_id,base_sha,state,
attempt_count,leased_by,produced_sha FROM tasks ORDER BY task_id"""

STAGE = r"""
import hashlib, os, sqlite3, sys
from pathlib import Path
raw = sys.stdin.buffer.read(67108865)
if not 100 <= len(raw) <= 67108864:
    raise SystemExit("raw_size_invalid")
if raw[:16] != b"SQLite format 3\x00":
    raise SystemExit("db_header_invalid")
if hashlib.sha256(raw).hexdigest() != os.environ["EXPECTED_DB_SHA256"]:
    raise SystemExit("db_digest_invalid")
target = Path("/data/codex-worker-pool.db")
with target.open("xb") as dst:
    dst.write(raw)
    dst.flush()
    os.fsync(dst.fileno())
db = sqlite3.connect(target.as_uri() + "?mode=ro", uri=True)
try:
    db.execute("PRAGMA query_only=ON")
    if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise SystemExit("db_integrity_invalid")
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise SystemExit("db_foreign_key_invalid")
finally:
    db.close()
print("ISOLATED_DB_STAGED")
"""

READBACK = r"""
import hashlib, json, sqlite3
from pathlib import Path
p = Path("/data/codex-worker-pool.db")
db = sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)
try:
    db.execute("PRAGMA query_only=ON")
    if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise SystemExit("db_integrity_invalid")
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise SystemExit("db_foreign_key_invalid")
    rows = db.execute(""" + repr(IDENTITY_SQL) + r""").fetchall()
    workers = db.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
    schema = [x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    digest = hashlib.sha256(json.dumps(rows, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    print(json.dumps({"digest":digest,"task_count":len(rows),"workers":workers,
                     "work_runs_present":"work_runs" in schema}))
finally:
    db.close()
"""


class RehearsalBlocked(RuntimeError):
    """Only fixed error codes; never propagate private CLI output."""


def require(value: bool, reason: str) -> None:
    if not value:
        raise RehearsalBlocked(reason)


def preflight(host: str, source_sha: str, checkout_sha: str,
              worker_sha: str, correlation: str, confirmation: str) -> None:
    require(host.upper() == HOST and confirmation == CONFIRM
            and SHA.fullmatch(source_sha) is not None and source_sha == checkout_sha
            and worker_sha == WORKER_SHA and CORR.fullmatch(correlation) is not None,
            "preflight_identity_rejected")


def fingerprint(raw: bytes) -> dict:
    """All active leases forbidden; completed/failed historical rows are retained."""
    backup.verify_restore(raw)
    db = sqlite3.connect(":memory:")
    try:
        db.deserialize(raw)
        db.execute("PRAGMA query_only=ON")
        rows = db.execute(IDENTITY_SQL).fetchall()
        workers = db.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
    finally:
        db.close()
    active = {"leased", "running", "validating"}
    require(len(rows) >= 2 and workers == 0
            and all(row[5] not in active and row[7] is None for row in rows),
            "snapshot_has_active_work_or_workers")
    required = {inventory.TASK_IDS[0], inventory.TASK_IDS[1]}
    require({row[0] for row in rows if row[0] in required} == required
            and all(row[5] == "queued" and row[6] == 0 for row in rows
                    if row[0] in required), "fixed_task_snapshot_diverged")
    return {"digest": hashlib.sha256(json.dumps(rows, separators=(",", ":"),
                   sort_keys=True).encode()).hexdigest(),
            "task_count": len(rows), "workers": 0}


def docker_binary(arguments: list[str], raw: bytes, expected: str) -> None:
    require(100 <= len(raw) <= backup.MAX_BYTES
            and hashlib.sha256(raw).hexdigest() == expected, "backup_digest_invalid")
    try:
        process = subprocess.run(["docker", *arguments], input=raw,
                                 capture_output=True, timeout=40, check=False)
    except (OSError, subprocess.SubprocessError):
        raise RehearsalBlocked("isolated_import_unavailable") from None
    require(process.returncode == 0 and process.stdout.strip() == b"ISOLATED_DB_STAGED",
            "isolated_import_rejected")


def docker(*args: str, timeout: int = 30, can_fail: bool = False) -> tuple[int, str]:
    try:
        return canary.execute(["docker", *args], timeout=timeout, can_fail=can_fail)
    except canary.CanaryBlocked:
        raise RehearsalBlocked("docker_command_rejected") from None


def docker_json(*args: str) -> dict:
    try:
        result = json.loads(docker(*args)[1])
    except (TypeError, ValueError):
        raise RehearsalBlocked("docker_json_invalid") from None
    require(isinstance(result, list) and len(result) == 1
            and isinstance(result[0], dict), "docker_identity_invalid")
    return result[0]


def cleanup_container(name: str, correlation: str) -> None:
    code, raw = docker("container", "inspect", name, can_fail=True)
    if code:
        return
    try:
        obj = json.loads(raw)
        require(len(obj) == 1 and obj[0]["Name"] == "/" + name
                and obj[0]["Config"]["Labels"].get("com.reqsys.workerpool.restore")
                == correlation, "cleanup_container_not_owned")
    except (KeyError, TypeError, ValueError):
        raise RehearsalBlocked("cleanup_container_identity_invalid") from None
    docker("rm", "-f", name)


def cleanup_volume(name: str, correlation: str) -> None:
    code, raw = docker("volume", "inspect", name, can_fail=True)
    if code:
        return
    try:
        obj = json.loads(raw)
        require(len(obj) == 1 and obj[0]["Name"] == name
                and obj[0]["Labels"].get("com.reqsys.workerpool.restore") == correlation,
                "cleanup_volume_not_owned")
    except (KeyError, TypeError, ValueError):
        raise RehearsalBlocked("cleanup_volume_identity_invalid") from None
    docker("volume", "rm", name)


def cleanup_image(tag: str, correlation: str) -> None:
    code, raw = docker("image", "inspect", tag, can_fail=True)
    if code:
        return
    try:
        obj = json.loads(raw)
        require(len(obj) == 1
                and obj[0]["Config"]["Labels"].get("com.reqsys.workerpool.restore")
                == correlation, "cleanup_image_not_owned")
    except (KeyError, TypeError, ValueError):
        raise RehearsalBlocked("cleanup_image_identity_invalid") from None
    docker("image", "rm", tag)


def verify_sql(container: str, expected: dict, *, migrated: bool) -> None:
    try:
        info = json.loads(docker("exec", "--user", "reqsys", container,
                                 "python", "-c", READBACK)[1])
    except (ValueError, TypeError):
        raise RehearsalBlocked("isolated_readback_invalid") from None
    require(info.get("digest") == expected["digest"]
            and info.get("task_count") == expected["task_count"]
            and info.get("workers") == 0
            and info.get("work_runs_present") is migrated,
            "isolated_task_identity_or_schema_changed")


def get(port: int, path: str, token: str) -> tuple[int, dict]:
    allowed = (path in {"/health", "/openapi.json", "/v1/contract"}
               or path in {"/v1/tasks/" + x for x in inventory.TASK_IDS}
               or path in {"/v1/tasks/" + x + "/diagnostics"
                           for x in inventory.TASK_IDS})
    require(port in {18098, 18099} and allowed, "http_target_rejected")
    req = Request("http://127.0.0.1:" + str(port) + path,
                  headers={"Authorization": "Bearer " + token})
    opener = build_opener(ProxyHandler({}), canary.NoRedirect())
    try:
        with opener.open(req, timeout=4) as response:
            raw = response.read(100001)
            require(len(raw) <= 100000, "http_response_oversized")
            return response.status, json.loads(raw)
    except HTTPError as exc:
        return exc.code, {}
    except (OSError, URLError, ValueError):
        raise RehearsalBlocked("loopback_http_unavailable") from None


def ready(port: int, token: str) -> None:
    for _ in range(26):
        try:
            status, data = get(port, "/health", token)
            if status == 200 and data.get("status") == "healthy":
                return
        except RehearsalBlocked as exc:
            if str(exc) != "loopback_http_unavailable":
                raise
        time.sleep(0.5)
    raise RehearsalBlocked("isolated_runtime_not_ready")


def run_process(name: str, image: str, volume: str, token_file: Path,
                correlation: str, port: int) -> None:
    require(IMAGE.fullmatch(image) is not None, "image_not_digest_pinned")
    target = "/run/secrets/canary-token"
    docker("run", "--detach", "--name", name, "--network", "bridge",
           "--publish", f"127.0.0.1:{port}:8097",
           "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "--pids-limit", "128", "--memory", "512m",
           "--label", "com.reqsys.workerpool.restore=" + correlation,
           "--mount", f"type=volume,src={volume},dst=/data",
           "--mount", f"type=bind,src={token_file},dst={target},readonly",
           "--env", "CODEX_WORKER_POOL_DB=/data/codex-worker-pool.db",
           "--env", "CODEX_WORKER_POOL_API_TOKEN_FILE=" + target,
           "--env", "CODEX_WORKER_POOL_EXPECTED_RULES_SHA=" + RULES_SHA,
           "--env", "CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS=300",
           image, timeout=30)
    obj = docker_json("container", "inspect", name)
    conf, host = obj.get("Config") or {}, obj.get("HostConfig") or {}
    mounts = {m.get("Destination"): m for m in obj.get("Mounts") or []}
    token = mounts.get(target) or {}
    data = mounts.get("/data") or {}
    bindings = (host.get("PortBindings") or {}).get("8097/tcp") or []
    require(obj.get("Name") == "/" + name and obj.get("Image") == image
            and (obj.get("State") or {}).get("Running") is True
            and host.get("Privileged") is False and host.get("ReadonlyRootfs") is True
            and "ALL" in (host.get("CapDrop") or [])
            and conf.get("User") == "reqsys"
            and len(bindings) == 1 and bindings[0].get("HostIp") == "127.0.0.1"
            and bindings[0].get("HostPort") == str(port)
            and len(mounts) == 2 and data.get("Type") == "volume"
            and data.get("Name") == volume and data.get("RW") is True
            and token.get("Type") == "bind" and token.get("RW") is False
            and canary._same_token_mount_source(str(token.get("Source") or ""),
                                                  str(token_file.resolve())),
            "isolated_container_policy_invalid")


def rehearse(*, source_sha: str, worker_sha: str, correlation: str,
             confirmation: str, host: str, checkout_sha: str,
             workspace: Path, private_dir: Path) -> dict:
    preflight(host, source_sha, checkout_sha, worker_sha, correlation, confirmation)
    source = canary.source_checkout(workspace, worker_sha)
    require(private_dir.is_dir() and not private_dir.is_symlink(),
            "private_location_rejected")
    live_before = canary.legacy_readback()
    require(live_before[2]["worker_count"] == 0
            and all(t["state"] == "queued" and t["attempt_count"] == 0
                    and not t["leased"] for t in live_before[2]["tasks"]),
            "live_tasks_not_quiescent")
    legacy_image = live_before[1]
    require(IMAGE.fullmatch(legacy_image) is not None, "legacy_image_untrusted")
    old = docker_json("image", "inspect", legacy_image)
    require(old.get("Id") == legacy_image
            and (old.get("Config") or {}).get("User") == "reqsys",
            "legacy_image_missing_or_untrusted")
    result = backup.snapshot(
        host=host, expected_sha=source_sha, observed_sha=checkout_sha,
        correlation_id=correlation, confirm=backup.CONFIRM,
        run_text=inventory._docker, run_binary=backup.docker_backup,
        encrypt=lambda v: backup.dpapi(v, encrypt=True),
        decrypt=lambda v: backup.dpapi(v, encrypt=False), root=private_dir)
    require(result["result"] == "WORKER_POOL_DEV_PROTECTED_BACKUP_VERIFIED"
            and result["separate_file_restore_verified"] is True
            and result["container_image_sha256"] == legacy_image.removeprefix("sha256:"),
            "physical_snapshot_unverified")
    encrypted = private_dir / ("workerpool-" + correlation + ".dpapi")
    require(encrypted.is_file() and not encrypted.is_symlink(),
            "protected_snapshot_unavailable")
    raw = backup.dpapi(encrypted.read_bytes(), encrypt=False)
    expected = fingerprint(raw)
    require(hashlib.sha256(raw).hexdigest() == result["backup_plain_sha256"]
            and expected["task_count"] == result["task_rows"],
            "snapshot_digest_or_identity_mismatch")
    suffix = correlation.removeprefix("pc24x7-workerpool-restore-")
    name, reverted = "wp-restore-" + suffix, "wp-back-" + suffix
    volume, tag = "wp-rvol-" + suffix, "wp-restore:" + suffix
    stage = None
    image_id = ""
    try:
        require(all(docker(*cmd, can_fail=True)[0] != 0 for cmd in (
            ("container", "inspect", name), ("container", "inspect", reverted),
            ("volume", "inspect", volume), ("image", "inspect", tag))),
            "isolated_resource_collision")
        stage = Path(tempfile.mkdtemp(prefix="workerpool-rehearsal-", dir=private_dir))
        canary.safe_staging(source, stage / "context")
        token_path = stage / "synthetic-token"
        with token_path.open("x", encoding="utf-8") as fh:
            fh.write(secrets.token_urlsafe(48))
        token = token_path.read_text(encoding="utf-8").strip()
        docker("build", "--quiet", "--pull",
               "--label", "org.opencontainers.image.revision=" + worker_sha,
               "--label", "com.reqsys.workerpool.restore=" + correlation,
               "-t", tag, str(stage / "context"), timeout=140)
        image = docker_json("image", "inspect", tag)
        image_id = image.get("Id", "")
        require(IMAGE.fullmatch(image_id) is not None
                and image.get("Config", {}).get("Labels", {}).get(
                    "org.opencontainers.image.revision") == worker_sha,
                "candidate_image_not_attested")
        docker("volume", "create", "--label",
               "com.reqsys.workerpool.restore=" + correlation, volume)
        arguments = ["run", "--rm", "--network", "none", "--user", "reqsys",
                     "--read-only", "--cap-drop", "ALL",
                     "--security-opt", "no-new-privileges",
                     "--mount", f"type=volume,src={volume},dst=/data",
                     "--env", "EXPECTED_DB_SHA256=" + result["backup_plain_sha256"],
                     image_id, "python", "-c", STAGE]
        docker_binary(arguments, raw, result["backup_plain_sha256"])
        del raw
        run_process(name, image_id, volume, token_path, correlation, 18098)
        ready(18098, token)
        require(get(18098, "/openapi.json", token)[1].get("info", {}).get("version")
                == "1.4.0", "candidate_version_invalid")
        require(get(18098, "/v1/contract", token)[1].get("contract_version")
                == "v1", "candidate_contract_invalid")
        require(get(18098, "/v1/contract", "invalid")[0] == 401,
                "candidate_negative_auth_failed")
        for task_id in inventory.TASK_IDS:
            status, data = get(18098, "/v1/tasks/" + task_id + "/diagnostics", token)
            require(status == 200 and data.get("task", {}).get("state") == "queued"
                    and data.get("claim_performed") is False,
                    "candidate_persisted_task_mismatch")
        verify_sql(name, expected, migrated=True)
        cleanup_container(name, correlation)
        run_process(reverted, legacy_image, volume, token_path, correlation, 18099)
        ready(18099, token)
        require(get(18099, "/openapi.json", token)[1].get("info", {}).get("version")
                == "1.2.0", "rollback_runtime_not_legacy")
        require(get(18099, "/v1/tasks/" + inventory.TASK_IDS[0], token)[1].get(
                "state") == "queued", "rollback_task_readback_invalid")
        verify_sql(reverted, expected, migrated=True)
        require(live_before == canary.legacy_readback(),
                "live_service_changed_during_isolated_rehearsal")
    finally:
        cleanup_failed = False
        for fn, item in ((cleanup_container, reverted), (cleanup_container, name),
                         (cleanup_volume, volume), (cleanup_image, tag)):
            try:
                fn(item, correlation)
            except RehearsalBlocked:
                cleanup_failed = True
        if stage is not None:
            try:
                shutil.rmtree(stage)
            except OSError:
                cleanup_failed = True
        if cleanup_failed:
            raise RehearsalBlocked("isolated_cleanup_failed")
    return {
        "result": "WORKER_POOL_DEV_REAL_COPY_ROLLBACK_VERIFIED",
        "host": HOST, "environment": "dev", "source_sha": source_sha,
        "worker_pool_sha": worker_sha, "rules_sha": RULES_SHA,
        "correlation_id": correlation, "candidate_image_id": image_id,
        "legacy_image_id": legacy_image, "task_count": expected["task_count"],
        "encrypted_private_backup": True, "physical_snapshot_restored_to_candidate": True,
        "candidate_contract_v1": True, "rollback_to_legacy_copy_passed": True,
        "independent_task_readback": True, "negative_auth_control": True,
        "isolated_volume_cleaned": True, "candidate_container_cleaned": True,
        "legacy_container_unchanged": True, "live_database_modified": False,
        "claim_performed": False, "production_touched": False,
        "secrets_exposed": False, "cutover_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--worker-pool-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        require(os.name == "nt" and socket.gethostname().upper() == HOST,
                "physical_windows_host_required")
        root = backup.private_directory(os.environ.get("LOCALAPPDATA", ""))
        checkout = canary.execute(["git", "-C", str(ROOT), "rev-parse", "HEAD"])[1]
        data = rehearse(source_sha=args.expected_sha, worker_sha=args.worker_pool_sha,
                        correlation=args.correlation_id, confirmation=args.confirm,
                        host=socket.gethostname(), checkout_sha=checkout,
                        workspace=Path(os.environ.get("GITHUB_WORKSPACE", "")),
                        private_dir=root)
        rc = 0
    except (RehearsalBlocked, backup.BackupBlocked, canary.CanaryBlocked) as error:
        data = {"result": "WORKER_POOL_DEV_RESTORE_REHEARSAL_BLOCKED",
                "reason": str(error), "cutover_ready": False,
                "production_touched": False, "secrets_exposed": False}
        rc = 2
    except Exception:
        data = {"result": "WORKER_POOL_DEV_RESTORE_REHEARSAL_BLOCKED",
                "reason": "rehearsal_unavailable", "cutover_ready": False,
                "production_touched": False, "secrets_exposed": False}
        rc = 2
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps(data, sort_keys=True))
    return rc


if __name__ == "__main__":
    sys.exit(main())
