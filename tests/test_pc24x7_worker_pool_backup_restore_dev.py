"""Synthetic and contract tests: guarded DEV backup, WAL, replay and no leakage."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("workerpool_backup_test", ROOT / "scripts/pc24x7_worker_pool_backup_restore_dev.py")
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def seed(tmp_path: Path, *, missing: bool = False) -> Path:
    path = tmp_path / "workerpool.sqlite"
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE tasks(task_id TEXT PRIMARY KEY,issue_number INTEGER,request_id TEXT,
                           base_sha TEXT,state TEXT,attempt_count INTEGER,private_note TEXT);
        CREATE TABLE workers(worker_id TEXT);
        CREATE TABLE repository_lanes(repository TEXT);
        CREATE TABLE worker_repository_affinity(worker_id TEXT);
    """)
    for i, task_id in enumerate(module.inventory.TASK_IDS):
        if missing and i == 1:
            continue
        db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?)",
                   (task_id, 2546+i, ("4f6f18810783cdc6872f04f1",
                    "9a9783d5ac78199eacfd13c0")[i],
                    "14232beac63c8d202f90bed1cf23df8680a54b2e",
                    "queued", 0, "TOP_SECRET_TEST_MARKER"))
    db.commit()
    db.close()
    return path


def captured_backup(path: Path) -> bytes:
    command = module.SQL_BACKUP.replace(
        'Path("/data/codex-worker-pool.db")', f"Path({str(path)!r})")
    result = subprocess.run([sys.executable, "-c", command],
                            capture_output=True, check=True, timeout=10)
    return result.stdout


def fake_docker():
    inspect = {
        "Id": "b"*64, "Image": "sha256:"+"a"*64, "State": {"Running": True},
        "Config": {
            "Labels": {"com.docker.compose.service": "codex-worker-pool"},
            "Env": ["CODEX_WORKER_POOL_DB=/data/codex-worker-pool.db",
                    "CODEX_WORKER_POOL_API_TOKEN_FILE=/run/secrets/codex_worker_pool_api_token"]},
        "NetworkSettings": {"Ports": {"8097/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8097"}]}},
        "Mounts": [{"Destination": "/data", "Type": "volume"},
                   {"Destination": "/run/secrets/codex_worker_pool_api_token",
                    "Type": "bind", "RW": False, "Source": "VERY_PRIVATE_PATH"}]}
    calls = []
    def run(args):
        calls.append(args)
        if args[0] == "ps":
            return "b"*12 + "\n"
        if args[0] == "inspect":
            return json.dumps([inspect])
        raise AssertionError("unexpected docker subcommand")
    return run, calls, inspect


def toy_encrypt(raw: bytes) -> bytes:
    return b"fake-encrypted:" + raw[::-1]


def toy_decrypt(raw: bytes) -> bytes:
    if not raw.startswith(b"fake-encrypted:"):
        raise ValueError("damaged ciphertext")
    return raw.removeprefix(b"fake-encrypted:")[::-1]


def invoke(tmp_path: Path, db: Path, **overrides):
    run, calls, inspect = fake_docker()
    fixture = captured_backup(db)
    settings = {
        "host": module.HOST, "expected_sha": "a"*40, "observed_sha": "a"*40,
        "correlation_id": "workerpool-backup-test", "confirm": module.CONFIRM,
        "run_text": run, "run_binary": lambda cid: fixture,
        "encrypt": toy_encrypt, "decrypt": toy_decrypt, "root": tmp_path / "private"
    }
    settings["root"].mkdir(exist_ok=True)
    settings.update(overrides)
    return module.snapshot(**settings), calls


def test_wal_online_backup_and_independent_sqlite_restore(tmp_path: Path):
    db = seed(tmp_path)
    raw = captured_backup(db)
    assert raw[:16] == b"SQLite format 3\x00"
    assert raw[18:20] == b"\x01\x01"
    summary = module.verify_restore(raw)
    assert summary["tasks_preserved"] == 2
    assert summary["task_rows"] == 2
    first, commands = invoke(tmp_path, db)
    assert first["result"] == "WORKER_POOL_DEV_PROTECTED_BACKUP_VERIFIED"
    assert first["private_encrypted_copy"] if "private_encrypted_copy" in first else first["encrypted_private_backup"]
    assert first["isolated_memory_restore_verified"] is True
    assert first["separate_file_restore_verified"] is False
    assert first["cutover_ready"] is False
    assert first["claim_performed"] is False and first["live_database_modified"] is False
    assert [args[0] for args in commands] == ["ps", "inspect"]
    path = next((tmp_path / "private").glob("*.dpapi"))
    assert b"TOP_SECRET_TEST_MARKER" not in path.read_bytes()
    assert "TOP_SECRET_TEST_MARKER" not in json.dumps(first)
    assert "VERY_PRIVATE_PATH" not in json.dumps(first)
    second, _ = invoke(tmp_path, db)
    assert second["replayed"] is True
    assert first["backup_cipher_sha256"] == second["backup_cipher_sha256"]
    assert len(list((tmp_path / "private").glob("*.dpapi"))) == 1


@pytest.mark.parametrize("override", [
    {"host": "OTHER-PC"}, {"observed_sha": "b"*40}, {"confirm": "wrong"},
    {"expected_sha": "invalid"}, {"correlation_id": "../escape"},
])
def test_preconditions_block_before_docker(tmp_path: Path, override: dict):
    db = seed(tmp_path)
    calls, _, _ = fake_docker()
    with pytest.raises(module.BackupBlocked, match="host_sha_or_confirmation_invalid"):
        invoke(tmp_path, db, run_text=calls, **override)
    # run_text is never invoked by the function under invalid preconditions.


def test_missing_task_fails_without_persisting_backup(tmp_path: Path):
    db = seed(tmp_path, missing=True)
    with pytest.raises(module.BackupBlocked, match="restored_tasks_missing"):
        invoke(tmp_path, db)
    assert list((tmp_path / "private").glob("*.dpapi")) == []


def test_invalid_db_or_wal_flags_fail_closed(tmp_path: Path):
    db = seed(tmp_path)
    raw = captured_backup(db)
    for data in (b"not sqlite", raw[:20], raw[:18]+b"\x02\x02"+raw[20:]):
        with pytest.raises(module.BackupBlocked):
            module.verify_restore(data)


def test_corrupt_persistent_cipher_detected_on_replay(tmp_path: Path):
    db = seed(tmp_path)
    invoke(tmp_path, db)
    destination = next((tmp_path / "private").glob("*.dpapi"))
    destination.write_bytes(b"modified-cipher")
    with pytest.raises(module.BackupBlocked, match="snapshot_replay_decrypt_failed"):
        invoke(tmp_path, db)


def test_docker_unsafe_mount_is_refused_before_binary_read(tmp_path: Path):
    db = seed(tmp_path)
    safe, _, state = fake_docker()
    state["Mounts"][1]["RW"] = True
    called = []
    with pytest.raises(module.BackupBlocked, match="container_identity_unavailable"):
        invoke(tmp_path, db, run_text=safe, run_binary=lambda _: called.append(True))
    assert called == []


def test_never_declare_physical_cutover_ready():
    workflow = (ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml").read_text(encoding="utf-8")
    gateway = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text(encoding="utf-8")
    assert "          - backup-restore" in workflow
    assert "  backup-restore:" in workflow
    block = workflow.split("\n  backup-restore:\n", 1)[1]
    assert "SESSION_LAUNCH_OK" in block and "command_gateway.py" in block
    assert "pc24x7_worker_pool_backup_restore_dev.py" in block
    assert "BACKUP-WORKER-POOL-DEV-ISOLATED" in block
    assert "WORKER_POOL_DEV_PROTECTED_BACKUP_VERIFIED" in block
    assert "separate_file_restore_verified" in block
    assert "cutover_ready" in block
    assert "upload-artifact@" in block
    assert "mode='backup-restore'" in gateway and "-f mode=backup-restore" in gateway
    assert "github.event.issue.number == 1705" in gateway
    assert "github.event.comment.user.login == 'ericson-j-santos'" in gateway
    assert "github.event.comment.body == '/reqsys run pc24x7-worker-pool-backup-restore-dev'" in gateway
    assert " -f target_path=" not in gateway
