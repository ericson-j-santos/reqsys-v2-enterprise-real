#!/usr/bin/env python3
"""Read-only physical inventory of the current PC24x7 Worker Pool coordinator.

Only the approved DEV Docker compose service on loopback :8097 is eligible.
The SQLite connection is mode=ro/query_only and does not invoke the API
snapshot/reconciliation or claim any work. This tool never deploys anything.
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
HOST = "DESKTOP-PDQK954"
SERVICE = "codex-worker-pool"
DB_PATH = "/data/codex-worker-pool.db"
TOKEN_PATH = "/run/secrets/codex_worker_pool_api_token"
TASK_IDS = ("cwp-cdb85c31e3cc4e972f3094ab", "cwp-7d84018f3319356181ab9b47")
CONFIRM = "READ-WORKER-POOL-DEV-SQL-ONLY"
EVIDENCE = ROOT / "artifacts" / "pc24x7-worker-pool-inventory-dev" / "evidence.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
CID = re.compile(r"^[0-9a-f]{12,64}$")
CORRELATION = re.compile(r"^[a-z0-9][a-z0-9-]{7,139}$")


class InventoryBlocked(RuntimeError):
    """An allowlisted, non-sensitive error code only."""


# This code executes inside the *already running* coordinator container.
# It never invokes the application/store and never opens a writable database.
SQL_PROBE = r'''
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "/data/codex-worker-pool.db"
TASK_IDS = ("cwp-cdb85c31e3cc4e972f3094ab", "cwp-7d84018f3319356181ab9b47")
REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
NOW = datetime.now(timezone.utc)


def _age(timestamp):
    if not timestamp:
        return None
    try:
        value = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        return max(0, int((NOW - value.astimezone(timezone.utc)).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return None


def collect(db_path=DB_PATH):
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True, timeout=8, isolation_level=None)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        required = {"workers", "repository_lanes", "tasks", "worker_repository_affinity"}
        present = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required.issubset(present):
            raise RuntimeError("schema_incomplete")
        task_rows = db.execute(
            "SELECT task_id,repository,issue_number,request_id,state,base_sha,leased_by,"
            "attempt_count,max_attempts,produced_sha FROM tasks WHERE task_id IN (?,?)",
            TASK_IDS,
        ).fetchall()
        lane = db.execute(
            "SELECT enabled,max_in_flight FROM repository_lanes WHERE repository=?", (REPO,)
        ).fetchone()
        workers = db.execute(
            "SELECT worker_id,role,profile,gateway_ok,state_validated,rules_sha,last_heartbeat_at "
            "FROM workers WHERE role IN ('builder','validator') ORDER BY role,worker_id"
        ).fetchall()
        affinities = db.execute(
            "SELECT worker_id,repository FROM worker_repository_affinity"
        ).fetchall()
        busy = {row[0] for row in db.execute(
            "SELECT leased_by FROM tasks WHERE leased_by IS NOT NULL AND state IN ('leased','running','validating')"
        )}
        active = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE repository=? AND state IN ('leased','running','validating')", (REPO,)
        ).fetchone()[0]
        columns = {row[1] for row in db.execute("PRAGMA table_info(tasks)")}
        integrity = db.execute("PRAGMA quick_check(1)").fetchone()[0]
        db.rollback()
    finally:
        db.close()
    expected_rules = os.getenv("CODEX_WORKER_POOL_EXPECTED_RULES_SHA", "").strip().lower()
    heartbeat_ttl = int(os.getenv("CODEX_WORKER_POOL_HEARTBEAT_TTL_SECONDS", "90"))
    if heartbeat_ttl < 1 or heartbeat_ttl > 3600 or integrity != "ok":
        raise RuntimeError("integrity_or_configuration_blocked")
    by_task = {row["task_id"]: row for row in task_rows}
    payload_tasks = []
    for task_id in TASK_IDS:
        task = by_task.get(task_id)
        if task is None:
            raise RuntimeError("fixed_task_missing")
        expected_issue = 2546 if task_id == TASK_IDS[0] else 2547
        expected_request = "4f6f18810783cdc6872f04f1" if expected_issue == 2546 else "9a9783d5ac78199eacfd13c0"
        if (task["repository"] != REPO or task["issue_number"] != expected_issue
                or task["request_id"] != expected_request
                or task["base_sha"] != "14232beac63c8d202f90bed1cf23df8680a54b2e"):
            raise RuntimeError("fixed_task_identity_mismatch")
        payload_tasks.append({
            "task_id": task_id, "issue_number": expected_issue, "state": task["state"],
            "attempt_count": task["attempt_count"], "max_attempts": task["max_attempts"],
            "leased": task["leased_by"] is not None, "produced_sha_present": bool(task["produced_sha"]),
        })
    affinity_map = {}
    for item in affinities:
        affinity_map.setdefault(item["worker_id"], set()).add(item["repository"])
    views = []
    for worker in workers:
        age = _age(worker["last_heartbeat_at"])
        reasons = []
        if age is None or age > heartbeat_ttl:
            reasons.append("offline_or_stale")
        if worker["profile"] != "NORMAL":
            reasons.append("profile_not_normal")
        if not worker["gateway_ok"] or not worker["state_validated"]:
            reasons.append("governance_not_ready")
        if not expected_rules or worker["rules_sha"] != expected_rules:
            reasons.append("rules_sha_unavailable_or_mismatch")
        if worker["worker_id"] in busy:
            reasons.append("worker_busy")
        allowed = affinity_map.get(worker["worker_id"], set())
        if allowed and REPO not in allowed:
            reasons.append("repository_affinity_mismatch")
        if lane is None or not lane["enabled"]:
            reasons.append("lane_disabled_or_missing")
        if lane and worker["role"] == "builder" and active >= lane["max_in_flight"]:
            reasons.append("lane_capacity_reached")
        views.append({
            "id_hash_prefix": hashlib.sha256(worker["worker_id"].encode()).hexdigest()[:16],
            "role": worker["role"], "profile": worker["profile"],
            "heartbeat_fresh": age is not None and age <= heartbeat_ttl,
            "gateway_ok": bool(worker["gateway_ok"]),
            "state_validated": bool(worker["state_validated"]),
            "rules_sha_matches": bool(expected_rules and worker["rules_sha"] == expected_rules),
            "eligible_precheck": len(reasons) == 0,
            "reasons": reasons,
        })
    return {
        "schema_version": "1.0.0", "read_mode": "sqlite_mode_ro",
        "db_quick_check": "ok", "legacy_progress_column_present": "last_material_progress_at" in columns,
        "tasks": payload_tasks,
        "lane": {"configured": lane is not None, "enabled": bool(lane["enabled"]) if lane else False,
                 "max_in_flight": lane["max_in_flight"] if lane else None, "active_count": active},
        "worker_count": len(views), "builders_registered": sum(w["role"] == "builder" for w in views),
        "validators_registered": sum(w["role"] == "validator" for w in views),
        "eligible_builders": sum(w["role"] == "builder" and w["eligible_precheck"] for w in views),
        "eligible_validators": sum(w["role"] == "validator" and w["eligible_precheck"] for w in views),
        "workers": views, "claim_performed": False, "snapshot_called": False,
        "requeue_performed": False, "runtime_mutated": False, "secrets_exposed": False,
    }


if __name__ == "__main__":
    print(json.dumps(collect(), sort_keys=True))
'''


def _docker(args: list[str]) -> str:
    try:
        outcome = subprocess.run(["docker", *args], check=True, text=True, capture_output=True, timeout=20)
        if len(outcome.stdout) > 150_000:
            raise InventoryBlocked("docker_output_too_large")
        return outcome.stdout
    except (subprocess.SubprocessError, OSError) as exc:
        raise InventoryBlocked("docker_read_unavailable") from exc


def _container_id(run: Callable[[list[str]], str]) -> tuple[str, str]:
    raw = run(["ps", "--filter", f"label=com.docker.compose.service={SERVICE}", "--format", "{{.ID}}"])
    ids = [i.strip() for i in raw.splitlines() if i.strip()]
    if not ids or len(ids) > 10 or any(not CID.fullmatch(i) for i in ids):
        raise InventoryBlocked("worker_pool_container_identity_invalid")
    try:
        payload = json.loads(run(["inspect", *ids]))
    except (ValueError, TypeError) as exc:
        raise InventoryBlocked("container_inspect_invalid") from exc
    options = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict) or (item.get("State") or {}).get("Running") is not True:
            continue
        if (item.get("Config") or {}).get("Labels", {}).get("com.docker.compose.service") != SERVICE:
            continue
        ports = (item.get("NetworkSettings") or {}).get("Ports", {}).get("8097/tcp") or []
        if not any(p.get("HostIp") == "127.0.0.1" and p.get("HostPort") == "8097" for p in ports):
            continue
        mounts = item.get("Mounts") or []
        db = [m for m in mounts if m.get("Destination") == "/data" and m.get("Type") in ("volume", "bind")]
        token = [m for m in mounts if m.get("Destination") == TOKEN_PATH and m.get("Type") == "bind" and m.get("RW") is False]
        cfg_env = (item.get("Config") or {}).get("Env") or []
        if len(db) != 1 or len(token) != 1 or f"CODEX_WORKER_POOL_DB={DB_PATH}" not in cfg_env:
            continue
        if f"CODEX_WORKER_POOL_API_TOKEN_FILE={TOKEN_PATH}" not in cfg_env:
            continue
        container_id = str(item.get("Id") or "").lower()
        image = str(item.get("Image") or "").lower()
        if CID.fullmatch(container_id) and re.fullmatch(r"sha256:[a-f0-9]{64}", image):
            options.append((container_id, image))
    if len(options) != 1:
        raise InventoryBlocked("worker_pool_container_not_unique_or_untrusted")
    return options[0]


def _validate_inventory(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("read_mode") != "sqlite_mode_ro":
        raise InventoryBlocked("readonly_inventory_invalid")
    expected = [2546, 2547]
    rows = raw.get("tasks")
    if not isinstance(rows, list) or len(rows) != 2:
        raise InventoryBlocked("fixed_tasks_unavailable")
    task_keys = {"task_id", "issue_number", "state", "attempt_count", "max_attempts", "leased", "produced_sha_present"}
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != task_keys:
            raise InventoryBlocked("fixed_tasks_payload_invalid")
        if row.get("task_id") != TASK_IDS[i] or row.get("issue_number") != expected[i]:
            raise InventoryBlocked("fixed_tasks_mismatch")
        if row.get("state") not in {"queued", "leased", "running", "validating", "blocked", "failed", "completed"}:
            raise InventoryBlocked("task_state_invalid")
        if type(row.get("attempt_count")) is not int or type(row.get("max_attempts")) is not int or not (0 <= row["attempt_count"] <= row["max_attempts"] <= 20):
            raise InventoryBlocked("task_attempts_invalid")
        if type(row.get("leased")) is not bool or type(row.get("produced_sha_present")) is not bool:
            raise InventoryBlocked("task_boolean_fields_invalid")
    workers = raw.get("workers")
    if not isinstance(workers, list) or len(workers) > 50:
        raise InventoryBlocked("workers_invalid")
    allow = {"id_hash_prefix", "role", "profile", "heartbeat_fresh", "gateway_ok", "state_validated", "rules_sha_matches", "eligible_precheck", "reasons"}
    reasons_allow = {"offline_or_stale", "profile_not_normal", "governance_not_ready", "rules_sha_unavailable_or_mismatch", "worker_busy", "repository_affinity_mismatch", "lane_disabled_or_missing", "lane_capacity_reached"}
    for worker in workers:
        if not isinstance(worker, dict) or set(worker) != allow:
            raise InventoryBlocked("worker_evidence_invalid")
        if (type(worker.get("reasons")) is not list or any(r not in reasons_allow for r in worker["reasons"])
                or any(type(worker.get(k)) is not bool for k in ("heartbeat_fresh", "gateway_ok", "state_validated", "rules_sha_matches", "eligible_precheck"))):
            raise InventoryBlocked("worker_boolean_or_reason_invalid")
        if worker.get("role") not in ("builder", "validator") or worker.get("profile") not in ("NORMAL", "ESTUDO"):
            raise InventoryBlocked("worker_role_or_profile_invalid")
        if not re.fullmatch(r"[a-f0-9]{16}", str(worker.get("id_hash_prefix"))):
            raise InventoryBlocked("worker_id_hash_invalid")
    if raw.get("db_quick_check") != "ok" or raw.get("legacy_progress_column_present") is not True:
        raise InventoryBlocked("db_integrity_or_compatibility_blocked")
    lane = raw.get("lane")
    if not isinstance(lane, dict) or set(lane) != {"configured", "enabled", "max_in_flight", "active_count"}:
        raise InventoryBlocked("lane_payload_invalid")
    if type(lane["configured"]) is not bool or type(lane["enabled"]) is not bool or type(lane["active_count"]) is not int or lane["active_count"] < 0:
        raise InventoryBlocked("lane_types_invalid")
    if lane["max_in_flight"] is not None and (type(lane["max_in_flight"]) is not int or lane["max_in_flight"] < 1):
        raise InventoryBlocked("lane_capacity_invalid")
    if any(type(raw.get(k)) is not int or raw[k] < 0 for k in ("worker_count", "builders_registered", "validators_registered", "eligible_builders", "eligible_validators")):
        raise InventoryBlocked("worker_counts_invalid")
    if raw["worker_count"] != len(workers) or raw["builders_registered"] + raw["validators_registered"] != len(workers):
        raise InventoryBlocked("worker_counts_mismatch")
    if any(raw.get(k) is not False for k in ("claim_performed", "snapshot_called", "requeue_performed", "runtime_mutated", "secrets_exposed")):
        raise InventoryBlocked("read_only_contract_violated")
    # Whitelist output, never propagate arbitrary SQL, docker, paths or error strings.
    allowed = {"schema_version", "read_mode", "db_quick_check", "legacy_progress_column_present", "tasks", "lane", "worker_count", "builders_registered", "validators_registered", "eligible_builders", "eligible_validators", "workers", "claim_performed", "snapshot_called", "requeue_performed", "runtime_mutated", "secrets_exposed"}
    if set(raw) != allowed:
        raise InventoryBlocked("unexpected_inventory_keys")
    return raw


def probe(*, host: str, expected_sha: str, observed_sha: str, correlation_id: str, confirm: str, run: Callable[[list[str]], str]) -> dict[str, Any]:
    if confirm != CONFIRM or host.upper() != HOST or not SHA40.fullmatch(expected_sha) or observed_sha != expected_sha or not CORRELATION.fullmatch(correlation_id):
        raise InventoryBlocked("host_sha_or_confirmation_invalid")
    container_id, image_id = _container_id(run)
    try:
        data = json.loads(run(["exec", "--user", "reqsys", container_id, "python", "-c", SQL_PROBE]))
    except (json.JSONDecodeError, TypeError) as exc:
        raise InventoryBlocked("sqlite_inventory_invalid_json") from exc
    inventory = _validate_inventory(data)
    return {
        "result": "WORKER_POOL_PHYSICAL_INVENTORY_READ_OK", "host": HOST,
        "source_sha": expected_sha, "correlation_id": correlation_id,
        "container_image_id_sha256": image_id.removeprefix("sha256:"),
        "docker_inspect_read_only": True, "sql_mode_ro": True,
        "environment": "dev", "production_touched": False,
        "inventory": inventory,
    }


def _head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True, timeout=10).stdout.strip().lower()
    except (OSError, subprocess.SubprocessError) as exc:
        raise InventoryBlocked("checkout_unavailable") from exc


def _write_evidence(payload: dict[str, Any]) -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        if socket.gethostname().upper() != HOST:
            raise InventoryBlocked("host_mismatch")
        result = probe(host=socket.gethostname(), expected_sha=args.expected_sha, observed_sha=_head(),
                       correlation_id=args.correlation_id, confirm=args.confirm, run=_docker)
        code = 0
    except InventoryBlocked as exc:
        result = {"result": "WORKER_POOL_PHYSICAL_INVENTORY_BLOCKED", "reason": str(exc),
                  "production_touched": False, "runtime_mutated": False, "secrets_exposed": False}
        code = 2
    except Exception:
        result = {"result": "WORKER_POOL_PHYSICAL_INVENTORY_BLOCKED", "reason": "inventory_unavailable",
                  "production_touched": False, "runtime_mutated": False, "secrets_exposed": False}
        code = 2
    _write_evidence(result)
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
