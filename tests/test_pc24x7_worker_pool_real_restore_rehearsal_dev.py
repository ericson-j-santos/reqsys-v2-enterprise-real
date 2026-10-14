"""Synthetic guards for an isolated real-backup Worker Pool 1.4 -> 1.2 rehearsal."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pc24x7_worker_pool_real_restore_rehearsal_dev.py"
spec = importlib.util.spec_from_file_location("workerpool_restore_rehearsal_test", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SHA = "a" * 40
CORR = "pc24x7-workerpool-restore-38491207347-1"


def settings():
    return (module.HOST, SHA, SHA, module.WORKER_SHA, CORR, module.CONFIRM)


def fixture(*, missing=False, worker=False, leased=False):
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
    CREATE TABLE tasks (
      task_id TEXT PRIMARY KEY, repository TEXT, issue_number INTEGER,
      request_id TEXT, base_sha TEXT, state TEXT, attempt_count INTEGER,
      leased_by TEXT, produced_sha TEXT);
    CREATE TABLE workers (worker_id TEXT);
    CREATE TABLE repository_lanes (repository TEXT);
    CREATE TABLE worker_repository_affinity (worker_id TEXT);
    """)
    for idx, task_id in enumerate(module.inventory.TASK_IDS):
        if missing and idx == 1:
            continue
        connection.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
            (task_id, "ericson-j-santos/reqsys-v2-enterprise-real", 2546 + idx,
             ("4f6f18810783cdc6872f04f1", "9a9783d5ac78199eacfd13c0")[idx],
             "14232beac63c8d202f90bed1cf23df8680a54b2e",
             "leased" if leased and idx == 0 else "queued",
             1 if leased and idx == 0 else 0,
             "builder" if leased and idx == 0 else None, None))
    if worker:
        connection.execute("INSERT INTO workers VALUES('test-builder')")
    # A completed historical row must not falsely block recovery.
    connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
                       ("cwp-" + "f" * 24, "ericson-j-santos/reqsys-v2-enterprise-real",
                        100, "historical", "1" * 40, "completed", 2, None, "2" * 40))
    connection.commit()
    raw = connection.serialize()
    connection.close()
    return raw


def test_exact_host_shas_and_correlation_before_io():
    module.preflight(*settings())
    pairs = [(0, "OTHER"), (1, "badsha"), (2, "b" * 40),
             (3, "b" * 40), (4, "../oops"), (5, "UNVERIFIED")]
    with patch.object(module, "docker", side_effect=AssertionError("forbidden IO")):
        for position, value in pairs:
            args = list(settings())
            args[position] = value
            with pytest.raises(module.RehearsalBlocked, match="preflight_identity_rejected"):
                module.preflight(*args)


def test_legacy_sqlite_fingerprint_preserves_historical_and_target_states():
    raw = fixture()
    assert raw[:16] == b"SQLite format 3\x00"
    first = module.fingerprint(raw)
    assert first["task_count"] == 3 and first["workers"] == 0
    assert first == module.fingerprint(raw)


@pytest.mark.parametrize("invalid", [
    {"missing": True}, {"worker": True}, {"leased": True},
])
def test_invalid_snapshot_fails_closed(invalid):
    with pytest.raises((module.RehearsalBlocked, module.backup.BackupBlocked)):
        module.fingerprint(fixture(**invalid))


def test_import_real_sqlite_snapshot_to_separate_file_and_negative_controls(tmp_path):
    raw = fixture()
    target = tmp_path / "isolated-copy.db"
    source = module.STAGE.replace("/data/codex-worker-pool.db", str(target))
    expected = hashlib.sha256(raw).hexdigest()
    import os
    env = dict(os.environ, EXPECTED_DB_SHA256=expected)
    first = subprocess.run([sys.executable, "-c", source], input=raw,
                           capture_output=True, timeout=8, check=False, env=env)
    assert first.returncode == 0
    assert first.stdout.strip() == b"ISOLATED_DB_STAGED"
    assert target.read_bytes() == raw
    second = subprocess.run([sys.executable, "-c", source], input=raw,
                            capture_output=True, timeout=8, check=False, env=env)
    assert second.returncode != 0
    assert target.read_bytes() == raw
    bad_env = dict(env, EXPECTED_DB_SHA256="0" * 64)
    target.unlink()
    bad = subprocess.run([sys.executable, "-c", source], input=raw,
                         capture_output=True, timeout=8, check=False, env=bad_env)
    assert bad.returncode != 0 and not target.exists()
    read = module.READBACK.replace("/data/codex-worker-pool.db", str(tmp_path / "missing"))
    missing = subprocess.run([sys.executable, "-c", read],
                             capture_output=True, timeout=8, check=False)
    assert missing.returncode != 0
    # No synthetic record or token may appear in the sanitized receipt.
    assert "historical" not in first.stdout.decode()


def test_sqlite_independent_readback_control(tmp_path):
    raw = fixture()
    target = tmp_path / "restored.db"
    target.write_bytes(raw)
    code = module.READBACK.replace("/data/codex-worker-pool.db", str(target))
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            timeout=8, check=True)
    observed = json.loads(result.stdout)
    assert observed == {**module.fingerprint(raw), "work_runs_present": False}
    connection = sqlite3.connect(target)
    connection.execute("UPDATE tasks SET state='failed' WHERE issue_number=2546")
    connection.commit()
    connection.close()
    changed = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             timeout=8, check=True)
    assert json.loads(changed.stdout)["digest"] != observed["digest"]


def test_binary_import_rejects_digest_before_docker_and_never_logs_bytes():
    raw = fixture()
    with patch.object(module.subprocess, "run", side_effect=AssertionError("subprocess must not run")):
        with pytest.raises(module.RehearsalBlocked, match="backup_digest_invalid"):
            module.docker_binary(["run", "--rm"], raw, "f" * 64)

def test_import_requires_interactive_stdin_and_no_network():
    raw = fixture()
    source_sha = hashlib.sha256(raw).hexdigest()
    with patch.object(module.subprocess, "run", side_effect=AssertionError("must not run")):
        with pytest.raises(module.RehearsalBlocked, match="isolated_import_args_invalid"):
            module.docker_binary(["run", "--rm", "--network", "none"], raw, source_sha)
        with pytest.raises(module.RehearsalBlocked, match="isolated_import_args_invalid"):
            module.docker_binary(["run", "--rm", "--interactive", "--network", "host"], raw, source_sha)


def test_claim_and_external_url_banned_before_any_request():
    with patch.object(module, "build_opener", side_effect=AssertionError("external request")):
        for port, path in [(443, "/health"), (8097, "/health"),
                           (18098, "/v1/claims"), (18099, "/v1/snapshot"),
                           (18098, "/v1/workers")]:
            with pytest.raises(module.RehearsalBlocked, match="http_target_rejected"):
                module.get(port, path, "secret")


def test_cleanup_never_removes_foreign_container_or_volume():
    foreign = [{"Name": "/wp-restore-38491207347-1",
                "Config": {"Labels": {"com.reqsys.workerpool.restore": "other"}}}]
    calls = []

    def fake_docker(*args, **_):
        calls.append(args)
        return (0, json.dumps(foreign))

    with patch.object(module, "docker", side_effect=fake_docker):
        with pytest.raises(module.RehearsalBlocked, match="cleanup_container_not_owned"):
            module.cleanup_container("wp-restore-38491207347-1", CORR)
    assert not any(args[0] == "rm" for args in calls)


def test_workflow_gateway_scope_and_rehearsal_cannot_approve_cutover():
    workflow = (ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml").read_text()
    gateway = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text()
    assert "\n  restore-rehearsal:\n" in workflow
    block = workflow.split("\n  restore-rehearsal:\n", 1)[1]
    for term in ("SESSION_LAUNCH_OK", "command_gateway.py",
                 "pc24x7_worker_pool_real_restore_rehearsal_dev.py",
                 "RESTORE-WORKER-POOL-DEV-ISOLATED",
                 "WORKER_POOL_DEV_REAL_COPY_ROLLBACK_VERIFIED",
                 "cutover_ready", "if-no-files-found: error"):
        assert term in block
    cmd = "/reqsys run pc24x7-worker-pool-real-restore-dev"
    assert f"github.event.comment.body == '{cmd}'" in gateway
    assert "mode='restore-rehearsal'" in gateway
    assert "-f mode=restore-rehearsal" in gateway
    assert "github.event.issue.number == 1705" in gateway
    assert "github.event.comment.user.login == 'ericson-j-santos'" in gateway
    source = SCRIPT.read_text()
    for term in ('"cutover_ready": False', '"claim_performed": False',
                 '"live_database_modified": False', '"production_touched": False',
                 '"secrets_exposed": False'):
        assert term in source
    assert "docker compose" not in source
    assert "snapshot(" in source and "docker_binary(" in source
