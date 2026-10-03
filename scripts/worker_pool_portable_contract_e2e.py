#!/usr/bin/env python3
"""E2E portátil do consumidor ReqSys contra o Work Orchestrator v1 real."""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import pending_development_worker_pool_bridge as bridge  # noqa: E402

SHA40 = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
ISSUE_NUMBER = 2020
DEFAULT_POOL_URL = "http://127.0.0.1:18097"


def validate_sha(value: str, reason: str) -> str:
    normalized = value.strip().lower()
    if not SHA40.fullmatch(normalized):
        raise bridge.BridgeError(reason)
    return normalized


def git_sha(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise bridge.BridgeError("portable_e2e_git_sha_unavailable") from exc
    return completed.stdout.strip().lower()


def contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(contains_key(item, key) for item in value)
    return False


def wait_for_health(
    process: subprocess.Popen[bytes],
    pool_url: str,
    token: str,
    *,
    timeout_seconds: float = 30.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise bridge.BridgeError("portable_e2e_worker_pool_process_exited")
        try:
            code, payload = bridge.http_request("GET", f"{pool_url}/health", token, None)
        except bridge.BridgeError:
            time.sleep(0.5)
            continue
        if code == 200 and payload.get("status") == "healthy":
            return
        time.sleep(0.5)
    raise bridge.BridgeError("portable_e2e_worker_pool_startup_timeout")


def prove_negative_auth(pool_url: str) -> None:
    try:
        bridge.http_request(
            "GET",
            f"{pool_url}/v1/contract",
            "portable-e2e-invalid-token",
            None,
        )
    except bridge.BridgeError as exc:
        if str(exc) == "worker_pool_http_401":
            return
        raise bridge.BridgeError("portable_e2e_negative_auth_unexpected") from exc
    raise bridge.BridgeError("portable_e2e_negative_auth_not_enforced")


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_e2e(
    *,
    reqsys_sha: str,
    worker_pool_root: Path,
    worker_pool_sha: str,
    rules_sha: str,
    correlation_id: str,
    pool_url: str,
) -> dict[str, Any]:
    reqsys_sha = validate_sha(reqsys_sha, "portable_e2e_reqsys_sha_invalid")
    worker_pool_sha = validate_sha(worker_pool_sha, "portable_e2e_worker_pool_sha_invalid")
    rules_sha = validate_sha(rules_sha, "portable_e2e_rules_sha_invalid")
    correlation_id = correlation_id.strip()
    if not correlation_id:
        raise bridge.BridgeError("portable_e2e_correlation_id_invalid")

    pool_root = worker_pool_root.resolve()
    if not (pool_root / "app" / "main.py").is_file():
        raise bridge.BridgeError("portable_e2e_worker_pool_checkout_invalid")
    if git_sha(ROOT) != reqsys_sha:
        raise bridge.BridgeError("portable_e2e_reqsys_sha_mismatch")
    if git_sha(pool_root) != worker_pool_sha:
        raise bridge.BridgeError("portable_e2e_worker_pool_sha_mismatch")

    pool_url = bridge.validate_pool_url(pool_url)
    parsed = urlparse(pool_url)
    port = parsed.port
    if port is None or not (1024 <= port <= 65535):
        raise bridge.BridgeError("portable_e2e_pool_port_invalid")

    with tempfile.TemporaryDirectory(prefix="reqsys-worker-pool-portable-") as tmp_raw:
        tmp = Path(tmp_raw)
        token_file = tmp / "api-token"
        token = secrets.token_urlsafe(32)
        token_file.write_text(token + "\n", encoding="utf-8")
        try:
            token_file.chmod(0o600)
        except OSError:
            pass

        env = os.environ.copy()
        env.update(
            {
                "CODEX_WORKER_POOL_DB": str(tmp / "worker-pool.db"),
                "CODEX_WORKER_POOL_API_TOKEN_FILE": str(token_file),
                "CODEX_WORKER_POOL_EXPECTED_RULES_SHA": rules_sha,
                "CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS": "300",
            }
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=pool_root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wait_for_health(process, pool_url, token)
            prove_negative_auth(pool_url)

            lane_payload = {
                "repository": EXPECTED_REPOSITORY,
                "enabled": False,
                "max_in_flight": 1,
                "correlation_id": f"{correlation_id}-lane"[:128],
            }
            lane_code, lane = bridge.http_request(
                "POST",
                f"{pool_url}/v1/repositories",
                token,
                lane_payload,
            )
            if (
                lane_code != 200
                or lane.get("repository") != EXPECTED_REPOSITORY
                or lane.get("enabled") is not False
            ):
                raise bridge.BridgeError("portable_e2e_lane_disable_failed")

            report = bridge.direct_report(
                EXPECTED_REPOSITORY,
                ISSUE_NUMBER,
                "main",
                correlation_id,
            )
            handoff = bridge.enqueue_local_work(
                report,
                base_sha=reqsys_sha,
                pool_url=pool_url,
                token=token,
                allow_legacy_fallback=False,
                allow_work_fallback=False,
            )
            if (
                handoff.get("result") != "WORKER_POOL_ENQUEUED"
                or handoff.get("contract_mode") != "v1"
                or handoff.get("dispatch_modes") != ["work_v1"]
                or handoff.get("legacy_fallback_used") is not False
                or handoff.get("work_orchestrator_preferred") is not True
            ):
                raise bridge.BridgeError("portable_e2e_work_v1_not_strict")

            items = handoff.get("items") or []
            if len(items) != 1:
                raise bridge.BridgeError("portable_e2e_item_count_invalid")
            item = items[0]
            work_id = str(item.get("work_id") or "")
            task_id = str(item.get("task_id") or "")
            if (
                not work_id
                or not task_id
                or item.get("replay_created") is not False
                or item.get("independent_readback") is not True
            ):
                raise bridge.BridgeError("portable_e2e_handoff_evidence_invalid")

            work_code, work = bridge.http_request(
                "GET",
                f"{pool_url}/v1/work/{work_id}",
                token,
                None,
            )
            if work_code != 200:
                raise bridge.BridgeError("portable_e2e_work_readback_failed")
            task = work.get("task")
            if (
                work.get("work_id") != work_id
                or work.get("task_id") != task_id
                or not isinstance(task, dict)
                or task.get("task_id") != task_id
                or task.get("repository") != EXPECTED_REPOSITORY
                or task.get("issue_number") != ISSUE_NUMBER
                or task.get("base_sha") != reqsys_sha
            ):
                raise bridge.BridgeError("portable_e2e_work_readback_mismatch")

            snapshot_code, snapshot = bridge.http_request(
                "GET",
                f"{pool_url}/v1/snapshot",
                token,
                None,
            )
            if snapshot_code != 200:
                raise bridge.BridgeError("portable_e2e_snapshot_failed")
            lane_readback = next(
                (
                    row
                    for row in snapshot.get("repositories") or []
                    if row.get("repository") == EXPECTED_REPOSITORY
                ),
                None,
            )
            task_readback = next(
                (
                    row
                    for row in snapshot.get("tasks") or []
                    if row.get("task_id") == task_id
                ),
                None,
            )
            if not isinstance(lane_readback, dict) or lane_readback.get("enabled") is not False:
                raise bridge.BridgeError("portable_e2e_lane_readback_failed")
            if (
                not isinstance(task_readback, dict)
                or task_readback.get("state") != "queued"
                or task_readback.get("leased_by") is not None
            ):
                raise bridge.BridgeError("portable_e2e_task_became_executable")
            if snapshot.get("workers"):
                raise bridge.BridgeError("portable_e2e_unexpected_worker_registered")
            if contains_key(handoff, "lease_token") or contains_key(work, "lease_token"):
                raise bridge.BridgeError("portable_e2e_lease_token_leaked")

            return {
                "schema_version": "1.0.0",
                "result": "WORKER_POOL_PORTABLE_CONTRACT_E2E_PASSED",
                "environment": "github-hosted-ephemeral",
                "correlation_id": correlation_id,
                "reqsys_sha": reqsys_sha,
                "worker_pool_sha": worker_pool_sha,
                "rules_sha": rules_sha,
                "contract_name": bridge.EXPECTED_WORKER_POOL_CONTRACT_NAME,
                "contract_version": bridge.EXPECTED_WORKER_POOL_CONTRACT_VERSION,
                "dispatch_mode": "work_v1",
                "work_id": work_id,
                "task_id": task_id,
                "work_phase": work.get("phase"),
                "lane_enabled": False,
                "task_state": task_readback.get("state"),
                "leased_by": None,
                "replay_created": False,
                "independent_readback": True,
                "negative_auth_control": True,
                "legacy_fallback_used": False,
                "physical_runtime_validated": False,
                "production_touched": False,
                "deploy_executed": False,
                "secrets_persisted": False,
            }
        finally:
            stop_process(process)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="E2E portátil ReqSys -> Engineering Worker Pool Work v1"
    )
    parser.add_argument("--reqsys-sha", required=True)
    parser.add_argument("--worker-pool-root", type=Path, required=True)
    parser.add_argument("--worker-pool-sha", required=True)
    parser.add_argument("--rules-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--pool-url", default=DEFAULT_POOL_URL)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/worker-pool-portable-contract-e2e/evidence.json"),
    )
    args = parser.parse_args()

    try:
        result = run_e2e(
            reqsys_sha=args.reqsys_sha,
            worker_pool_root=args.worker_pool_root,
            worker_pool_sha=args.worker_pool_sha,
            rules_sha=args.rules_sha,
            correlation_id=args.correlation_id,
            pool_url=args.pool_url,
        )
        bridge.write_evidence(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (bridge.BridgeError, OSError) as exc:
        blocked = {
            "schema_version": "1.0.0",
            "result": "WORKER_POOL_PORTABLE_CONTRACT_E2E_BLOCKED",
            "reason": str(exc)[:240],
            "physical_runtime_validated": False,
            "production_touched": False,
            "deploy_executed": False,
        }
        bridge.write_evidence(args.output, blocked)
        print(json.dumps(blocked, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
