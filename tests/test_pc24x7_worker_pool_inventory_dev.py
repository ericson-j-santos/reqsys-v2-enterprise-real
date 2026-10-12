"""Synthetic physical read-only Worker Pool inventory with negative controls."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pc24x7_worker_pool_inventory_dev.py"
spec = importlib.util.spec_from_file_location("worker_inventory", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def seed_database(path: Path, *, study: bool = False, worker: bool = True) -> None:
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE tasks(task_id TEXT,repository TEXT,issue_number INTEGER,request_id TEXT,state TEXT,base_sha TEXT,leased_by TEXT,attempt_count INTEGER,max_attempts INTEGER,produced_sha TEXT,last_material_progress_at TEXT);
    CREATE TABLE repository_lanes(repository TEXT,enabled INTEGER,max_in_flight INTEGER);
    CREATE TABLE workers(worker_id TEXT,role TEXT,profile TEXT,gateway_ok INTEGER,state_validated INTEGER,rules_sha TEXT,last_heartbeat_at TEXT);
    CREATE TABLE worker_repository_affinity(worker_id TEXT,repository TEXT);
    """)
    for i, task_id in enumerate(mod.TASK_IDS):
        db.execute(
            "INSERT INTO tasks(task_id,repository,issue_number,request_id,state,base_sha,attempt_count,max_attempts) VALUES(?,?,?,?,?,?,?,?)",
            (task_id, "ericson-j-santos/reqsys-v2-enterprise-real", 2546+i,
             ["4f6f18810783cdc6872f04f1", "9a9783d5ac78199eacfd13c0"][i],
             "queued", "14232beac63c8d202f90bed1cf23df8680a54b2e", 0, 3),
        )
    db.execute("INSERT INTO repository_lanes VALUES(?,1,2)", ("ericson-j-santos/reqsys-v2-enterprise-real",))
    if worker:
        now = datetime.now(timezone.utc).isoformat()
        db.execute("INSERT INTO workers VALUES(?,?,?,?,?,?,?)", ("example-builder", "builder", "ESTUDO" if study else "NORMAL", 1, 1, "a"*40, now))
        db.execute("INSERT INTO workers VALUES(?,?,?,?,?,?,?)", ("example-validator", "validator", "NORMAL", 1, 1, "a"*40, now))
    db.commit()
    db.close()


def execute_embedded(db_path: Path, *, rules: str = "a"*40) -> dict:
    source = mod.SQL_PROBE.replace('DB_PATH = "/data/codex-worker-pool.db"', f'DB_PATH = {str(db_path)!r}')
    ns = {"__name__": "__main__"}
    original = os.environ.get("CODEX_WORKER_POOL_EXPECTED_RULES_SHA")
    os.environ["CODEX_WORKER_POOL_EXPECTED_RULES_SHA"] = rules
    stream = io.StringIO()
    try:
        with contextlib.redirect_stdout(stream):
            exec(compile(source, "<read-only-in-container>", "exec"), ns)
    finally:
        if original is None:
            os.environ.pop("CODEX_WORKER_POOL_EXPECTED_RULES_SHA", None)
        else:
            os.environ["CODEX_WORKER_POOL_EXPECTED_RULES_SHA"] = original
    return json.loads(stream.getvalue())


def test_sqlite_positive_negative_and_no_state_mutation(tmp_path: Path):
    db = tmp_path / "worker.sqlite"
    seed_database(db)
    before = list(sqlite3.connect(db).execute("SELECT task_id,state,attempt_count FROM tasks ORDER BY task_id"))
    first, second = execute_embedded(db), execute_embedded(db)
    after = list(sqlite3.connect(db).execute("SELECT task_id,state,attempt_count FROM tasks ORDER BY task_id"))
    assert before == after
    assert first["read_mode"] == "sqlite_mode_ro"
    assert first["db_quick_check"] == "ok"
    assert first["builders_registered"] == first["validators_registered"] == 1
    assert first["eligible_builders"] == first["eligible_validators"] == 1
    assert first["tasks"] == second["tasks"]
    assert "example-builder" not in repr(first)
    assert "example-validator" not in repr(first)
    assert not any(first[k] for k in ("claim_performed", "runtime_mutated", "requeue_performed", "snapshot_called", "secrets_exposed"))
    assert mod._validate_inventory(first) == first


def test_estudo_and_rules_mismatch_ineligible(tmp_path: Path):
    db = tmp_path / "worker.sqlite"
    seed_database(db, study=True)
    output = execute_embedded(db, rules="b"*40)
    assert output["eligible_builders"] == 0
    assert output["eligible_validators"] == 0
    builder = next(w for w in output["workers"] if w["role"] == "builder")
    assert "profile_not_normal" in builder["reasons"]
    assert "rules_sha_unavailable_or_mismatch" in builder["reasons"]


def test_missing_db_fails_closed(tmp_path: Path):
    with pytest.raises(sqlite3.OperationalError):
        execute_embedded(tmp_path / "absent.sqlite")
    assert not (tmp_path / "absent.sqlite").exists()


def fake_container():
    return {
        "Id": "b"*64, "Image": "sha256:"+"a"*64,
        "State": {"Running": True},
        "Config": {"Labels": {"com.docker.compose.service": "codex-worker-pool"},
                   "Env": ["CODEX_WORKER_POOL_DB=/data/codex-worker-pool.db",
                           "CODEX_WORKER_POOL_API_TOKEN_FILE=/run/secrets/codex_worker_pool_api_token"]},
        "NetworkSettings": {"Ports": {"8097/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8097"}]}},
        "Mounts": [
            {"Destination": "/data", "Type": "volume", "Name": "private-name"},
            {"Destination": "/run/secrets/codex_worker_pool_api_token", "Type": "bind", "RW": False,
             "Source": "SENSITIVE_HOST_PATH"},
        ],
    }


def test_docker_read_only_commands_and_host_sha_preconditions(tmp_path: Path):
    db = tmp_path / "worker.sqlite"
    seed_database(db)
    inner = execute_embedded(db)
    calls = []

    def docker(args):
        calls.append(args)
        if args[0] == "ps":
            return "b"*12 + "\n"
        if args[0] == "inspect":
            return json.dumps([fake_container()])
        if args[0] == "exec":
            return json.dumps(inner)
        raise AssertionError("unexpected_docker_verb")

    result = mod.probe(
        host=mod.HOST, expected_sha="a"*40, observed_sha="a"*40,
        correlation_id="worker-inventory-test", confirm=mod.CONFIRM, run=docker,
    )
    assert result["result"] == "WORKER_POOL_PHYSICAL_INVENTORY_READ_OK"
    assert [x[0] for x in calls] == ["ps", "inspect", "exec"]
    assert "SENSITIVE_HOST_PATH" not in json.dumps(result)
    assert "example-builder" not in json.dumps(result)
    assert "example-validator" not in json.dumps(result)
    for mismatch in (
        {"host": "another-host"}, {"observed_sha": "f"*40},
        {"confirm": "wrong"}, {"correlation_id": "!bad"},
    ):
        calls.clear()
        payload = {
            "host": mod.HOST, "expected_sha": "a"*40, "observed_sha": "a"*40,
            "correlation_id": "worker-inventory-test", "confirm": mod.CONFIRM, "run": docker,
        }
        payload.update(mismatch)
        with pytest.raises(mod.InventoryBlocked):
            mod.probe(**payload)
        assert calls == []


def test_untrusted_port_and_token_mount_denied():
    for patch in ("port", "token_rw", "duplicate"):
        def run(args):
            if args[0] == "ps":
                return "b"*12 + "\n"
            if args[0] == "inspect":
                obj = fake_container()
                if patch == "port":
                    obj["NetworkSettings"]["Ports"]["8097/tcp"][0]["HostIp"] = "0.0.0.0"
                if patch == "token_rw":
                    obj["Mounts"][1]["RW"] = True
                return json.dumps([obj, obj] if patch == "duplicate" else [obj])
            raise AssertionError("docker_exec_must_not_run")
        with pytest.raises(mod.InventoryBlocked):
            mod._container_id(run)


def test_reject_sensitive_inner_json_fields(tmp_path: Path):
    db = tmp_path / "worker.sqlite"
    seed_database(db)
    output = execute_embedded(db)
    output["task_secret"] = "would leak"
    with pytest.raises(mod.InventoryBlocked, match="unexpected_inventory_keys"):
        mod._validate_inventory(output)
