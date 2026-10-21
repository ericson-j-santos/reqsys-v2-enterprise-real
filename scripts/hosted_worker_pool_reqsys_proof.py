#!/usr/bin/env python3
"""Run the smallest real fenced ReqSys task against Worker Pool DEV authority."""
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
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
POOL_URL = "http://127.0.0.1:8097"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
WORKER_POOL_SHA = "5d8de580fea571404607aa80c7bd7637b4652db6"
STARTUP_FAILURE_CODES = frozenset({
    "postgres_driver_not_installed",
    "worker_pool_backend_invalid",
    "authority_credentials_acl_unverified",
    "authority_credentials_file_invalid",
    "authority_credentials_file_changed",
    "authority_schema_invalid",
    "authority_identity_invalid",
    "authority_connection_invalid",
    "authority_tls_identity_unverified",
    "authority_identity_mismatch",
    "authority_schema_version_mismatch",
    "authority_schema_incomplete",
    "authority_indexes_unverified",
    "authority_fence_guards_unverified",
    "authority_queue_order_unverified",
    "authority_connection_unavailable:unsupported_startup",
    "authority_connection_unavailable:channel_binding",
    "authority_connection_unavailable:authentication",
    "authority_connection_unavailable:dns",
    "authority_connection_unavailable:timeout",
    "authority_connection_unavailable:tls_certificate",
    "authority_connection_unavailable:tls",
    "authority_connection_unavailable:unknown",
})
STARTUP_LOG_LIMIT = 131072
SYSTEM_CA_BUNDLE = Path("/etc/ssl/certs/ca-certificates.crt")


class ProofError(RuntimeError):
    pass


def require(value: object, code: str) -> None:
    if not value:
        raise ProofError(code)


def git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ProofError("git_identity_unavailable") from exc
    value = result.stdout.strip().lower()
    require(SHA40.fullmatch(value) is not None, "git_identity_invalid")
    return value


def request_json(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        POOL_URL + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed loopback origin.
            raw = response.read(262145)
            require(len(raw) <= 262144, "worker_pool_response_too_large")
            value = json.loads(raw) if raw else {}
            require(isinstance(value, dict), "worker_pool_response_invalid")
            return int(response.status), value
    except HTTPError as exc:
        raw = exc.read(16385)
        value = {}
        if len(raw) <= 16384:
            try:
                decoded = json.loads(raw) if raw else {}
                if isinstance(decoded, dict):
                    value = decoded
            except (json.JSONDecodeError, UnicodeError):
                pass
        return int(exc.code), value
    except (URLError, TimeoutError, OSError) as exc:
        raise ProofError("worker_pool_unreachable") from exc


def expect(method: str, path: str, token: str, payload: dict | None, statuses: set[int]) -> dict:
    status, body = request_json(method, path, token, payload)
    require(status in statuses, "worker_pool_http_" + str(status))
    return body


def startup_failure_reason(log_path: Path) -> str:
    """Return one bounded public startup code without exposing raw service logs."""
    try:
        with log_path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - STARTUP_LOG_LIMIT))
            payload = stream.read(STARTUP_LOG_LIMIT)
    except OSError:
        return "worker_pool_process_exited"
    text = payload.decode("utf-8", errors="ignore").lower()
    matches = [(text.rfind(code), code) for code in STARTUP_FAILURE_CODES if code in text]
    if not matches:
        return "worker_pool_process_exited"
    return "worker_pool_startup_" + max(matches)[1].replace(":", "_")


def wait_ready(token: str, process: subprocess.Popen, log_path: Path) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ProofError(startup_failure_reason(log_path))
        try:
            status, body = request_json("GET", "/health", token)
            if status == 200 and body.get("status") == "healthy":
                return body
        except ProofError:
            pass
        time.sleep(0.25)
    if process.poll() is not None:
        raise ProofError(startup_failure_reason(log_path))
    raise ProofError("worker_pool_not_ready")


def write_private(path: Path, value: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, (value + "\n").encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def materialize_explicit_system_root(
    runtime_env: dict[str, str], private_dir: Path,
) -> dict[str, str]:
    """Bind libpq to the host CA bundle without exposing the private DSN."""
    try:
        source = Path(runtime_env["CODEX_WORKER_POOL_DATABASE_URL_FILE"])
        value = source.read_text(encoding="utf-8").strip()
        parsed = urlsplit(value)
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    except (KeyError, OSError, ValueError):
        raise ProofError("runtime_tls_profile_invalid") from None
    require(parsed.scheme == "postgresql" and bool(parsed.hostname),
            "runtime_tls_profile_invalid")
    roots = [item for key, item in pairs if key == "sslrootcert"]
    require(roots == ["system"], "runtime_tls_profile_invalid")
    require(SYSTEM_CA_BUNDLE.is_absolute() and SYSTEM_CA_BUNDLE.is_file(),
            "system_ca_bundle_unavailable")
    updated = [
        (key, str(SYSTEM_CA_BUNDLE) if key == "sslrootcert" else item)
        for key, item in pairs
    ]
    destination = private_dir / "runtime-explicit-root.url"
    write_private(destination, urlunsplit(parsed._replace(query=urlencode(updated))))
    result = dict(runtime_env)
    result["CODEX_WORKER_POOL_DATABASE_URL_FILE"] = str(destination)
    result["EWP_TEST_POSTGRES_URL_FILE"] = str(destination)
    return result


def run_task(reqsys_root: Path, arguments: list[str]) -> dict:
    command = [sys.executable, "-B", str(reqsys_root / "scripts/hosted_worker_pool_reqsys_task.py"), *arguments]
    try:
        result = subprocess.run(command, cwd=reqsys_root, check=False, capture_output=True,
                                text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProofError("reqsys_task_process_unavailable") from exc
    require(result.returncode == 0, "reqsys_task_process_failed")
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise ProofError("reqsys_task_receipt_invalid") from exc
    require(isinstance(payload, dict), "reqsys_task_receipt_invalid")
    return payload


def register(token: str, *, worker_id: str, role: str, rules_sha: str,
             correlation: str, root: Path) -> None:
    payload = {
        "worker_id": worker_id,
        "host": "github-hosted",
        "role": role,
        "profile": "NORMAL",
        "capacity_score": 10,
        "controller_version": "reqsys-hosted-handoff-v1",
        "rules_sha": rules_sha,
        "gateway_ok": True,
        "state_validated": True,
        "worktree_root": str(root),
        "correlation_id": correlation,
    }
    expect("POST", "/v1/workers", token, payload, {200})


def lease_body(worker_id: str, claim: dict, correlation: str) -> dict:
    lease = claim.get("lease")
    require(isinstance(lease, dict), "lease_missing")
    return {
        "worker_id": worker_id,
        "lease_token": lease.get("lease_token"),
        "lease_generation": lease.get("lease_generation"),
        "attempt_id": lease.get("attempt_id"),
        "correlation_id": correlation,
    }


def execute(args: argparse.Namespace, runtime_env: dict[str, str], token: str,
            reconciliation_token: str, private_dir: Path) -> dict:
    reqsys_root = args.reqsys_root.resolve()
    pool_root = args.worker_pool_root.resolve()
    require(git_head(reqsys_root) == args.base_sha, "reqsys_sha_mismatch")
    require(git_head(pool_root) == WORKER_POOL_SHA == args.worker_pool_sha,
            "worker_pool_sha_mismatch")
    require(os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
            and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and os.environ.get("GITHUB_REF") == "refs/heads/main"
            and os.environ.get("GITHUB_SHA") == args.base_sha,
            "github_identity_invalid")

    token_path = private_dir / "api-token"
    reconciliation_path = private_dir / "reconciliation-token"
    write_private(token_path, token)
    write_private(reconciliation_path, reconciliation_token)
    server_env = dict(os.environ)
    server_env.update(runtime_env)
    server_env.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(pool_root),
        "CODEX_WORKER_POOL_API_TOKEN_FILE": str(token_path),
        "CODEX_WORKER_POOL_RECONCILIATION_TOKEN_FILE": str(reconciliation_path),
        "CODEX_WORKER_POOL_EXPECTED_RULES_SHA": args.rules_sha,
        "CODEX_WORKER_POOL_FENCED_CUTOVER_ATTESTED": "0",
        "CODEX_WORKER_POOL_RECONCILE_INTERVAL_SECONDS": "300",
    })
    service_log = private_dir / "worker-pool-service.log"
    descriptor = os.open(service_log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    log_stream = os.fdopen(descriptor, "wb")
    server = subprocess.Popen(
        [sys.executable, "-B", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8097"],
        cwd=pool_root, env=server_env, stdin=subprocess.DEVNULL,
        stdout=log_stream, stderr=subprocess.STDOUT,
    )
    try:
        health = wait_ready(token, server, service_log)
        require(health.get("storage_backend") == "postgres"
                and health.get("fenced_cutover_enabled") is True,
                "qualified_fenced_authority_required")
        authority = expect("GET", "/v1/authority", token, None, {200})
        contract = expect("GET", "/v1/contract", token, None, {200})
        require(contract.get("contract_name") == "engineering-worker-pool"
                and contract.get("contract_version") == "v1",
                "worker_pool_contract_invalid")
        negative_status, _ = request_json("GET", "/v1/contract", "invalid-token")
        require(negative_status == 401, "negative_auth_control_failed")

        body = {
            "repository": REPOSITORY,
            "issue_number": args.issue_number,
            "request_id": args.request_id,
            "correlation_id": args.correlation_id,
            "priority": 10,
            "base_sha": args.base_sha,
            "target_branch": "main",
            "max_attempts": 2,
            "merge_policy": "governed",
            "fencing_required": True,
        }
        first_status, first = request_json("POST", "/v1/work", token, body)
        require(first_status in {200, 201} and isinstance(first.get("work"), dict),
                "work_create_failed")
        work = first["work"]
        task_id = str(work.get("task_id") or "")
        work_id = str(work.get("work_id") or "")
        require(task_id and work_id and work.get("task", {}).get("fencing_required") is True,
                "fenced_work_identity_invalid")
        replay = expect("POST", "/v1/work", token, body, {200})
        require(replay.get("created") is False
                and replay.get("work", {}).get("task_id") == task_id
                and replay.get("work", {}).get("work_id") == work_id,
                "work_replay_failed")

        run_id = os.environ["GITHUB_RUN_ID"]
        builder_id = ("reqsys-hosted-builder-" + run_id)[-128:]
        validator_id = ("reqsys-hosted-validator-" + run_id)[-128:]
        legacy_id = ("reqsys-legacy-negative-" + run_id)[-128:]
        register(token, worker_id=legacy_id, role="builder", rules_sha=args.rules_sha,
                 correlation=args.correlation_id + "-legacy", root=reqsys_root)
        legacy = expect("POST", "/v1/claims/exact", token, {
            "worker_id": legacy_id, "task_id": task_id,
            "correlation_id": args.correlation_id + "-legacy-claim", "lease_seconds": 60,
        }, {200})
        require(legacy.get("claimed") is False, "legacy_worker_admitted_fenced_task")

        task_receipt = args.output.parent / "task-receipt.json"
        execution_performed = False
        current = expect("GET", "/v1/tasks/" + task_id, token, None, {200})
        if current.get("state") == "queued":
            register(token, worker_id=builder_id, role="builder", rules_sha=args.rules_sha,
                     correlation=args.correlation_id + "-builder", root=reqsys_root)
            claim = expect("POST", "/v1/claims/fenced/exact", token, {
                "worker_id": builder_id, "task_id": task_id,
                "correlation_id": args.correlation_id + "-builder-claim", "lease_seconds": 180,
            }, {200})
            require(claim.get("claimed") is True, "fenced_builder_claim_failed")
            mutation = lease_body(builder_id, claim, args.correlation_id + "-builder")
            expect("POST", "/v1/tasks/" + task_id + "/start", token, mutation, {200})
            built = run_task(reqsys_root, [
                "build", "--root", str(reqsys_root), "--output", str(task_receipt),
                "--issue-number", str(args.issue_number), "--request-id", args.request_id,
                "--base-sha", args.base_sha,
            ])
            require(built.get("result") == "REQSYS_HOSTED_WORKER_TASK_EXECUTED"
                    and built.get("simulated") is False, "real_task_execution_failed")
            expect("POST", "/v1/tasks/" + task_id + "/validation", token,
                   {**mutation, "produced_sha": args.base_sha}, {200})

            register(token, worker_id=validator_id, role="validator", rules_sha=args.rules_sha,
                     correlation=args.correlation_id + "-validator", root=reqsys_root)
            validation_claim = expect("POST", "/v1/claims/fenced/exact", token, {
                "worker_id": validator_id, "task_id": task_id,
                "correlation_id": args.correlation_id + "-validator-claim", "lease_seconds": 180,
            }, {200})
            require(validation_claim.get("claimed") is True,
                    "fenced_validator_claim_failed")
            validated = run_task(reqsys_root, [
                "verify", "--root", str(reqsys_root), "--receipt", str(task_receipt),
                "--issue-number", str(args.issue_number), "--request-id", args.request_id,
                "--base-sha", args.base_sha,
            ])
            require(validated.get("result") == "REQSYS_HOSTED_WORKER_TASK_VALIDATED"
                    and validated.get("independent_process") is True,
                    "independent_task_validation_failed")
            expect("POST", "/v1/tasks/" + task_id + "/complete", token,
                   lease_body(validator_id, validation_claim,
                              args.correlation_id + "-validator-complete"), {200})
            execution_performed = True
        else:
            require(current.get("state") == "completed", "existing_task_not_terminal")

        evidence = {
            "validation_run_id": run_id,
            "validation_sha": args.base_sha,
            "evidence_reference": "github-actions:" + run_id + ":reqsys-hosted-worker-pool-proof",
            "independent_readback": True,
            "positive_control": True,
            "negative_control": True,
            "correlation_id": args.correlation_id + "-evidence",
        }
        recorded = expect("POST", "/v1/work/" + work_id + "/evidence", token, evidence, {200})
        require(recorded.get("evidence", {}).get("state") == "verified"
                and recorded.get("merge", {}).get("state") == "ready",
                "work_evidence_not_verified")
        final_task = expect("GET", "/v1/tasks/" + task_id, token, None, {200})
        require(final_task.get("state") == "completed"
                and final_task.get("fencing_required") is True,
                "final_task_readback_failed")
    finally:
        if server.poll() is None:
            server.terminate()
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        log_stream.close()

    provider_file = args.output.parent / "provider-readback.json"
    readback = run_task(reqsys_root, [
        "provider-readback", "--output", str(provider_file),
        "--worker-pool-root", str(pool_root), "--task-id", task_id,
        "--rules-sha", args.rules_sha,
    ])
    require(readback.get("result") == "REQSYS_HOSTED_WORKER_PROVIDER_READBACK_OK",
            "provider_readback_failed")
    return {
        "schema_version": "1.0.0",
        "result": "REQSYS_HOSTED_WORKER_POOL_PROOF_PASSED",
        "environment": "DEV",
        "reqsys_sha": args.base_sha,
        "worker_pool_sha": args.worker_pool_sha,
        "rules_sha": args.rules_sha,
        "issue_number": args.issue_number,
        "request_id": args.request_id,
        "correlation_id": args.correlation_id,
        "work_id": work_id,
        "task_id": task_id,
        "work_created_this_run": first.get("created") is True,
        "execution_performed_this_run": execution_performed,
        "real_reqsys_task_executed": True,
        "simulated": False,
        "fencing_required": True,
        "legacy_exact_claim_rejected": True,
        "replay_created": False,
        "negative_auth_status": negative_status,
        "independent_validator_process": True,
        "independent_postgres_readback": True,
        "storage_backend": health.get("storage_backend"),
        "authority_id": authority.get("authority_id"),
        "broker_identity": {"repository_id": os.environ.get("GITHUB_REPOSITORY_ID"),
                            "sha": args.base_sha, "run_id": os.environ.get("GITHUB_RUN_ID")},
        "production_touched": False,
        "deploy_executed": False,
        "merge_executed": False,
        "additional_cost_brl": "0.00",
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--reqsys-root", type=Path, required=True)
    result.add_argument("--worker-pool-root", type=Path, required=True)
    result.add_argument("--worker-pool-sha", required=True)
    result.add_argument("--rules-sha", required=True)
    result.add_argument("--issue-number", type=int, required=True)
    result.add_argument("--request-id", required=True)
    result.add_argument("--base-sha", required=True)
    result.add_argument("--correlation-id", required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    args.base_sha = args.base_sha.strip().lower()
    args.worker_pool_sha = args.worker_pool_sha.strip().lower()
    args.rules_sha = args.rules_sha.strip().lower()
    args.correlation_id = args.correlation_id.strip()
    args.request_id = args.request_id.strip()
    args.output = args.output.resolve()
    result = {"schema_version": "1.0.0", "result": "REQSYS_HOSTED_WORKER_POOL_PROOF_BLOCKED"}
    try:
        require(SHA40.fullmatch(args.base_sha) is not None
                and SHA40.fullmatch(args.worker_pool_sha) is not None
                and SHA40.fullmatch(args.rules_sha) is not None,
                "sha_invalid")
        require(args.issue_number > 0 and args.request_id and args.correlation_id,
                "proof_identity_invalid")
        require(os.environ.get("EWP_OWNER_GATEWAY_ATTESTED") == "1",
                "owner_gateway_attestation_missing")
        pool_root = args.worker_pool_root.resolve()
        sys.path.insert(0, str(pool_root))
        os.environ["EWP_IDENTITY_PROFILE"] = "reqsys-handoff-v1"
        from scripts.native_private_config import hydrate_github, runtime_environment

        identity = hydrate_github().get("identity")
        require(isinstance(identity, dict) and identity.get("sha") == args.base_sha,
                "broker_identity_mismatch")
        broker_runtime = runtime_environment()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="reqsys-hosted-proof-") as temporary:
            private_dir = Path(temporary)
            runtime = materialize_explicit_system_root(broker_runtime, private_dir)
            result = execute(args, runtime, secrets.token_urlsafe(32),
                             secrets.token_urlsafe(32), private_dir)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(json.dumps({"result": result["result"], "task_id": result["task_id"]},
                         sort_keys=True))
        return 0
    except (ProofError, KeyError, OSError, ValueError, subprocess.SubprocessError) as exc:
        reason = str(exc) if isinstance(exc, ProofError) else "proof_runtime_error"
        result["reason"] = reason
        result.update({"production_touched": False, "deploy_executed": False,
                       "merge_executed": False})
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                   encoding="utf-8")
        except OSError:
            pass
        print(json.dumps({"result": result["result"], "reason": reason}, sort_keys=True),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
