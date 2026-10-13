#!/usr/bin/env python3
"""Inputless DEV-only Worker Pool SQLite online backup and isolated restore.

The coordinator is inspected before a read-only SQLite backup. Sensitive SQLite
bytes are never logged or uploaded, and only DPAPI ciphertext is kept on disk.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
from typing import Callable

import pc24x7_worker_pool_inventory_dev as inventory

ROOT = Path(__file__).resolve().parents[1]
HOST = inventory.HOST
CONFIRM = "BACKUP-WORKER-POOL-DEV-ISOLATED"
EVIDENCE = ROOT / "artifacts" / "pc24x7-worker-pool-backup-restore-dev" / "evidence.json"
MAX_BYTES = 64 * 1024 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
CORRELATION = re.compile(r"[a-z0-9][a-z0-9-]{7,139}\Z")

# Fixed Python executed inside the existing, preverified coordinator only.
# SQLite Online Backup copies committed WAL data, without writing the source.
SQL_BACKUP = r"""
import sqlite3, sys
from pathlib import Path
src = sqlite3.connect(Path("/data/codex-worker-pool.db").as_uri()+"?mode=ro", uri=True, timeout=10)
try:
    src.execute("PRAGMA query_only=ON")
    pages = int(src.execute("PRAGMA page_count").fetchone()[0])
    size = int(src.execute("PRAGMA page_size").fetchone()[0])
    if pages < 1 or pages*size > 67108864:
        raise SystemExit(2)
    dst = sqlite3.connect(":memory:")
    try:
        src.backup(dst, pages=128, sleep=0.02)
        raw = bytearray(dst.serialize())
    finally:
        dst.close()
finally:
    src.close()
if len(raw) < 100 or len(raw) > 67108864 or raw[:16] != b"SQLite format 3\x00":
    raise SystemExit(3)
if raw[18:20] == b"\x02\x02":
    raw[18:20] = b"\x01\x01"
elif raw[18:20] != b"\x01\x01":
    raise SystemExit(4)
sys.stdout.buffer.write(raw)
"""


class BackupBlocked(RuntimeError):
    """Never includes raw process output or sensitive file paths."""


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def dpapi(value: bytes, *, encrypt: bool) -> bytes:
    if os.name != "nt" or not value or len(value) > MAX_BYTES + 8192:
        raise BackupBlocked("dpapi_unavailable_or_oversized")
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = ctypes.create_string_buffer(value)
    inp = _Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = _Blob()
    proc = crypt.CryptProtectData if encrypt else crypt.CryptUnprotectData
    proc.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                     ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                     ctypes.POINTER(_Blob)]
    proc.restype = wintypes.BOOL
    if not proc(ctypes.byref(inp), None, None, None, None, 1, ctypes.byref(output)):
        raise BackupBlocked("dpapi_operation_failed")
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        encoded = ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))
    if not encoded:
        raise BackupBlocked("dpapi_empty_output")
    return encoded


def verify_restore(raw: bytes) -> dict:
    """Independent isolated in-memory DB; never connects to live volume."""
    if not 100 <= len(raw) <= MAX_BYTES or raw[:16] != b"SQLite format 3\x00":
        raise BackupBlocked("backup_header_invalid")
    if raw[18:20] != b"\x01\x01":
        raise BackupBlocked("backup_journal_flags_invalid")
    try:
        db = sqlite3.connect(":memory:")
        try:
            db.deserialize(raw)
            db.execute("PRAGMA query_only=ON")
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise BackupBlocked("restored_integrity_invalid")
            if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise BackupBlocked("restored_foreign_key_invalid")
            names = {r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"tasks", "workers", "repository_lanes", "worker_repository_affinity"}.issubset(names):
                raise BackupBlocked("restored_schema_invalid")
            tasks = db.execute(
                "SELECT task_id,issue_number,request_id,base_sha,state,attempt_count "
                "FROM tasks WHERE task_id IN (?,?) ORDER BY issue_number",
                inventory.TASK_IDS,
            ).fetchall()
            expected_requests = ("4f6f18810783cdc6872f04f1", "9a9783d5ac78199eacfd13c0")
            if len(tasks) != 2:
                raise BackupBlocked("restored_tasks_missing")
            for i, row in enumerate(tasks):
                if (row[0] != inventory.TASK_IDS[i] or row[1] != 2546+i
                        or row[2] != expected_requests[i]
                        or row[3] != "14232beac63c8d202f90bed1cf23df8680a54b2e"
                        or row[4] not in {"queued", "leased", "running", "validating",
                                          "blocked", "completed", "failed"}
                        or type(row[5]) is not int or row[5] < 0):
                    raise BackupBlocked("restored_task_identity_invalid")
            total = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            return {"task_rows": total, "tasks_preserved": len(tasks),
                    "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        finally:
            db.close()
    except (sqlite3.Error, ValueError, OverflowError):
        raise BackupBlocked("isolated_restore_unavailable") from None


def docker_backup(container_id: str) -> bytes:
    try:
        process = subprocess.run(
            ["docker", "exec", "--user", "reqsys", container_id, "python", "-c", SQL_BACKUP],
            check=False, capture_output=True, timeout=65)
    except (OSError, subprocess.SubprocessError):
        raise BackupBlocked("docker_backup_unavailable") from None
    # STDOUT contains the unencrypted DB. Never forward process output.
    if process.returncode != 0 or not 100 <= len(process.stdout) <= MAX_BYTES:
        raise BackupBlocked("docker_backup_failed")
    return process.stdout


def private_directory(localappdata: str) -> Path:
    if os.name != "nt" or not localappdata:
        raise BackupBlocked("private_windows_storage_unavailable")
    base = Path(localappdata)
    if not base.is_absolute() or base.is_symlink():
        raise BackupBlocked("private_root_invalid")
    root = base / "ReqSys" / "WorkerPoolBackups"
    for component in (base, base/"ReqSys", root):
        if component.is_symlink() or (component.exists() and not component.is_dir()):
            raise BackupBlocked("private_root_redirected")
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise BackupBlocked("private_root_redirected")
    return root


def save_cipher(root: Path, key: str, cipher: bytes, sha: str,
                decrypt: Callable[[bytes], bytes]) -> tuple[bool, str]:
    destination = root / ("workerpool-" + key + ".dpapi")
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file() or destination.stat().st_nlink != 1:
            raise BackupBlocked("snapshot_path_redirected")
        stored = destination.read_bytes()
        try:
            previous = decrypt(stored)
        except Exception:
            raise BackupBlocked("snapshot_replay_decrypt_failed") from None
        if hashlib.sha256(previous).hexdigest() != sha:
            raise BackupBlocked("snapshot_replay_source_changed")
        return True, hashlib.sha256(stored).hexdigest()
    if not cipher:
        raise BackupBlocked("snapshot_cipher_missing")
    try:
        with destination.open("xb") as handle:
            handle.write(cipher)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        raise BackupBlocked("concurrent_snapshot")
    except OSError:
        raise BackupBlocked("private_snapshot_write_failed") from None
    return False, hashlib.sha256(cipher).hexdigest()


def snapshot(*, host: str, expected_sha: str, observed_sha: str,
             correlation_id: str, confirm: str, run_text: Callable[[list[str]], str],
             run_binary: Callable[[str], bytes], encrypt: Callable[[bytes], bytes],
             decrypt: Callable[[bytes], bytes], root: Path) -> dict:
    if (host.upper() != HOST or confirm != CONFIRM or not SHA40.fullmatch(expected_sha)
            or observed_sha != expected_sha or not CORRELATION.fullmatch(correlation_id)):
        raise BackupBlocked("host_sha_or_confirmation_invalid")
    try:
        container_id, image = inventory._container_id(run_text)
    except inventory.InventoryBlocked:
        raise BackupBlocked("container_identity_unavailable") from None
    raw = run_binary(container_id)
    first = verify_restore(raw)
    cipher = encrypt(raw)
    if not cipher or cipher == raw or decrypt(cipher) != raw:
        raise BackupBlocked("encryption_roundtrip_invalid")
    replay, cipher_sha = save_cipher(root, correlation_id, cipher, first["sha256"], decrypt)
    stored = (root / ("workerpool-" + correlation_id + ".dpapi")).read_bytes()
    if hashlib.sha256(stored).hexdigest() != cipher_sha or verify_restore(decrypt(stored)) != first:
        raise BackupBlocked("independent_encrypted_restore_mismatch")
    return {
        "result": "WORKER_POOL_DEV_PROTECTED_BACKUP_VERIFIED", "host": HOST,
        "source_sha": expected_sha, "environment": "dev",
        "correlation_id": correlation_id, "container_image_sha256": image.removeprefix("sha256:"),
        "backup_plain_sha256": first["sha256"], "backup_cipher_sha256": cipher_sha,
        "backup_bytes": first["bytes"], "task_rows": first["task_rows"],
        "tasks_preserved": first["tasks_preserved"], "replayed": replay,
        "dpapi_user_scope": True, "encrypted_private_backup": True,
        "isolated_memory_restore_verified": True, "separate_file_restore_verified": False,
        "cutover_ready": False, "live_database_modified": False,
        "claim_performed": False, "secrets_exposed": False, "production_touched": False,
    }


def head_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              text=True, capture_output=True, timeout=10).stdout.strip().lower()
    except (OSError, subprocess.SubprocessError):
        raise BackupBlocked("checkout_unavailable") from None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        if os.name != "nt" or socket.gethostname().upper() != HOST:
            raise BackupBlocked("host_not_eligible")
        root = private_directory(os.environ.get("LOCALAPPDATA", ""))
        result = snapshot(
            host=socket.gethostname(), expected_sha=args.expected_sha,
            observed_sha=head_sha(), correlation_id=args.correlation_id,
            confirm=args.confirm, run_text=inventory._docker,
            run_binary=docker_backup, encrypt=lambda b: dpapi(b, encrypt=True),
            decrypt=lambda b: dpapi(b, encrypt=False), root=root)
        code = 0
    except BackupBlocked as e:
        result = {"result": "WORKER_POOL_DEV_PROTECTED_BACKUP_BLOCKED", "reason": str(e),
                  "cutover_ready": False, "live_database_modified": False,
                  "secrets_exposed": False, "production_touched": False}
        code = 2
    except Exception:
        result = {"result": "WORKER_POOL_DEV_PROTECTED_BACKUP_BLOCKED",
                  "reason": "backup_or_restore_unavailable", "cutover_ready": False,
                  "live_database_modified": False, "secrets_exposed": False,
                  "production_touched": False}
        code = 2
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
