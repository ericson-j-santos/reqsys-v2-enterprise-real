#!/usr/bin/env python3
"""Bounded ReqSys task executed and independently read back through Worker Pool DEV."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


SHA40 = re.compile(r"^[0-9a-f]{40}$")
TASK_ID = re.compile(r"^cwp-[0-9a-f]{24}$")
INPUTS = (
    "AGENTS.md",
    ".github/workflows/codex-worker-pool-handoff.yml",
    "scripts/pending_development_worker_pool_bridge.py",
)


class TaskError(RuntimeError):
    pass


def require(value: object, code: str) -> None:
    if not value:
        raise TaskError(code)


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "task_input_invalid")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(root: Path, *, issue_number: int, request_id: str, base_sha: str) -> dict:
    require(root.is_absolute() and root.is_dir(), "source_root_invalid")
    require(issue_number > 0 and bool(request_id.strip()), "task_identity_invalid")
    require(SHA40.fullmatch(base_sha) is not None, "base_sha_invalid")
    return {
        "schema_version": "1.0.0",
        "result": "REQSYS_HOSTED_WORKER_TASK_EXECUTED",
        "repository": "ericson-j-santos/reqsys-v2-enterprise-real",
        "issue_number": issue_number,
        "request_id": request_id,
        "base_sha": base_sha,
        "operation": "inventory-governed-handoff-source",
        "inputs": {name: digest(root / name) for name in INPUTS},
        "source_files_read": len(INPUTS),
        "source_modified": False,
        "production_touched": False,
        "deploy_executed": False,
        "merge_executed": False,
        "simulated": False,
    }


def write_new(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def read_json(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536,
            "task_receipt_invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TaskError("task_receipt_invalid") from exc
    require(isinstance(value, dict), "task_receipt_invalid")
    return value


def provider_readback(worker_pool_root: Path, task_id: str, rules_sha: str) -> dict:
    require(worker_pool_root.is_absolute() and worker_pool_root.is_dir(),
            "worker_pool_root_invalid")
    require(TASK_ID.fullmatch(task_id) is not None, "task_id_invalid")
    require(SHA40.fullmatch(rules_sha) is not None, "rules_sha_invalid")
    sys.path.insert(0, str(worker_pool_root))
    from app.postgres_authority import PostgresAuthority, PostgresWorkerPoolStore

    authority = PostgresAuthority.from_file(
        Path(os.environ["CODEX_WORKER_POOL_DATABASE_URL_FILE"]),
        schema=os.environ["CODEX_WORKER_POOL_DB_SCHEMA"],
        authority_id=os.environ["CODEX_WORKER_POOL_AUTHORITY_ID"],
    )
    store = PostgresWorkerPoolStore(authority, expected_rules_sha=rules_sha)
    task = store.get_task(task_id)
    require(task["state"] == "completed" and bool(task.get("fencing_required")),
            "provider_readback_incomplete")
    require(task.get("lease_token") is None and task.get("leased_by") is None,
            "provider_readback_lease_present")
    return {
        "result": "REQSYS_HOSTED_WORKER_PROVIDER_READBACK_OK",
        "task_id": task_id,
        "state": task["state"],
        "fencing_required": True,
        "lease_released": True,
        "storage_backend": "postgres",
        "independent_process": True,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("mode", choices=("build", "verify", "provider-readback"))
    result.add_argument("--root", type=Path, default=Path.cwd())
    result.add_argument("--output", type=Path)
    result.add_argument("--receipt", type=Path)
    result.add_argument("--issue-number", type=int, default=0)
    result.add_argument("--request-id", default="")
    result.add_argument("--base-sha", default="")
    result.add_argument("--worker-pool-root", type=Path)
    result.add_argument("--task-id", default="")
    result.add_argument("--rules-sha", default="")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.mode == "provider-readback":
            require(args.output is not None and args.worker_pool_root is not None,
                    "provider_readback_arguments_missing")
            result = provider_readback(args.worker_pool_root.resolve(), args.task_id,
                                       args.rules_sha.lower())
            write_new(args.output, result)
        else:
            expected = receipt(args.root.resolve(), issue_number=args.issue_number,
                               request_id=args.request_id, base_sha=args.base_sha.lower())
            if args.mode == "build":
                require(args.output is not None, "task_output_missing")
                write_new(args.output, expected)
                result = expected
            else:
                require(args.receipt is not None, "task_receipt_missing")
                require(read_json(args.receipt) == expected, "task_receipt_mismatch")
                result = {
                    "result": "REQSYS_HOSTED_WORKER_TASK_VALIDATED",
                    "receipt_sha256": digest(args.receipt),
                    "independent_process": True,
                }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (TaskError, KeyError, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, TaskError) else "task_runtime_error"
        print(json.dumps({"result": "REQSYS_HOSTED_WORKER_TASK_BLOCKED", "reason": reason},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
