#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import reconcile_pc24x7_public_dev_runtime as public_runtime
import todo_global_hourly_cycle as cycle

CONFIRMATION = "RECONCILE-PC24X7-TODO-RUNTIME-DEV"
OVERLAY = Path("docker-compose.pc24x7-todo-runtime.yml")
ADAPTER_SECRET_NAME = "reqsys-pc24x7-todo-adapter-service-token"
PRODUCER_SECRET_NAME = "reqsys-pc24x7-todo-runtime-producer-token"
ADAPTER_SCOPE = "todo_global:upsert"
ADAPTER_LABEL = "pc24x7-todo-runtime-dev"
LOCAL_API_BASE = "http://127.0.0.1:8210"
LOCAL_GATEWAY_BASE = "http://127.0.0.1:8083"
RUNTIME_BASE = LOCAL_GATEWAY_BASE + "/runtime-core"


class ReconcileError(RuntimeError):
    pass


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> tuple[int, dict[str, Any]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Accept": "application/json", **(headers or {})},
    )
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(262_144).decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return int(response.status), parsed if isinstance(parsed, dict) else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read(262_144).decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        return int(exc.code), parsed if isinstance(parsed, dict) else {}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ReconcileError(f"network_error:{type(exc).__name__}") from None


def _compose_base(
    runtime_root: Path,
    project: str,
    config_files: list[Path],
    env_files: list[Path],
    *,
    include_overlay: bool,
) -> list[str]:
    command = [
        public_runtime._tool("docker"),
        "compose",
        "--project-directory",
        str(runtime_root),
        "-p",
        project,
    ]
    for env_file in env_files:
        command.extend(["--env-file", str(env_file)])
    overlay = (runtime_root / OVERLAY).resolve()
    seen: set[Path] = set()
    for config_file in config_files:
        resolved = config_file.resolve()
        if resolved == overlay:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        command.extend(["-f", str(resolved)])
    if include_overlay:
        if not overlay.is_file():
            raise ReconcileError("todo_runtime_overlay_missing")
        command.extend(["-f", str(overlay)])
    return command


def _wait_json(
    url: str,
    *,
    expected_sha: str | None = None,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status: int | None = None
    while time.monotonic() < deadline:
        try:
            status, payload = _request_json("GET", url, timeout=10)
            last_status = status
            if status == 200:
                data = payload.get("data", payload)
                if expected_sha is None:
                    return payload
                observed = str((data if isinstance(data, dict) else {}).get("build_sha") or "").lower()
                if observed == expected_sha.lower():
                    return payload
        except ReconcileError:
            pass
        time.sleep(2)
    raise ReconcileError(f"runtime_readiness_timeout:http_{last_status}")


def _secret_client(vault_name: str):
    try:
        from azure.identity import AzureCliCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError as exc:
        raise ReconcileError("azure_sdk_not_installed") from exc
    return SecretClient(
        vault_url=f"https://{vault_name}.vault.azure.net",
        credential=AzureCliCredential(),
    )


def _read_secret(client: Any, name: str) -> str:
    try:
        value = client.get_secret(name).value
    except Exception as exc:
        if exc.__class__.__name__ in {"ResourceNotFoundError", "SecretNotFound"}:
            return ""
        raise ReconcileError(f"keyvault_read_failed:{name}:{exc.__class__.__name__}") from None
    return str(value or "").strip()


def _adapter_readiness(token: str) -> int:
    status, _ = _request_json(
        "GET",
        LOCAL_API_BASE + "/api/internal/todo-global/readiness",
        headers={"X-Service-Token": token},
    )
    return status


def _mint_adapter_token(admin_jwt: str) -> str:
    if not admin_jwt:
        raise ReconcileError("admin_jwt_missing_for_adapter_token")
    status, payload = _request_json(
        "POST",
        LOCAL_API_BASE + "/v1/admin/service-tokens",
        headers={
            "Authorization": f"Bearer {admin_jwt}",
            "X-Correlation-Id": "pc24x7-todo-runtime-token-bootstrap",
        },
        payload={
            "label": ADAPTER_LABEL,
            "scopes": [ADAPTER_SCOPE],
            "expires_in_days": 90,
        },
    )
    if status not in {200, 201}:
        raise ReconcileError(f"adapter_service_token_mint_failed:http_{status}")
    try:
        token = str(payload["data"]["token"]).strip()
    except (KeyError, TypeError):
        raise ReconcileError("adapter_service_token_response_invalid") from None
    if not token:
        raise ReconcileError("adapter_service_token_empty")
    return token


def _ensure_tokens(client: Any, admin_jwt: str) -> tuple[str, str, dict[str, bool]]:
    adapter = _read_secret(client, ADAPTER_SECRET_NAME)
    adapter_created = False
    if adapter:
        readiness = _adapter_readiness(adapter)
        if readiness == 503:
            raise ReconcileError("todo_global_notion_configuration_missing")
        if readiness not in {200}:
            adapter = ""

    if not adapter:
        adapter = _mint_adapter_token(admin_jwt)
        client.set_secret(
            ADAPTER_SECRET_NAME,
            adapter,
            tags={
                "environment": "dev",
                "consumer": "reqsys-runtime",
                "scope": ADAPTER_SCOPE,
            },
        )
        adapter_created = True
        readiness = _adapter_readiness(adapter)
        if readiness == 503:
            raise ReconcileError("todo_global_notion_configuration_missing")
        if readiness != 200:
            raise ReconcileError(f"todo_global_adapter_not_ready:http_{readiness}")

    producer = _read_secret(client, PRODUCER_SECRET_NAME)
    producer_created = False
    if not producer:
        producer = secrets.token_urlsafe(32)
        client.set_secret(
            PRODUCER_SECRET_NAME,
            producer,
            tags={
                "environment": "dev",
                "consumer": "github-actions-and-runtime",
                "scope": "todo_runtime:producer",
            },
        )
        producer_created = True

    return adapter, producer, {
        "adapter_token_created": adapter_created,
        "producer_token_created": producer_created,
    }


def _execute_e2e(run_id: str, run_attempt: str, producer_token: str) -> dict[str, Any]:
    endpoint = RUNTIME_BASE + "/api/todo-events"
    event = cycle.build_event(run_id, run_attempt)
    cycle.assert_negative_control(endpoint, producer_token)
    accepted = cycle.submit(endpoint, event, producer_token)
    terminal = cycle.wait_terminal(
        RUNTIME_BASE,
        accepted["status_url"],
        producer_token,
        timeout_seconds=180,
        poll_seconds=5,
    )
    result = terminal.get("resultado") or {}
    if result.get("readback_verified") is not True:
        raise ReconcileError("todo_global_readback_not_verified")
    replay = cycle.submit(endpoint, event, producer_token)
    if replay["job_id"] != accepted["job_id"]:
        raise ReconcileError("todo_runtime_replay_created_second_job")
    if replay.get("duplicate_event") is not True:
        raise ReconcileError("todo_runtime_replay_not_duplicate")
    return {
        "event_id": event["event_id"],
        "job_id": accepted["job_id"],
        "terminal_status": terminal.get("status"),
        "readback_verified": True,
        "duplicate_event": True,
    }


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise ReconcileError(f"confirmation_required:{CONFIRMATION}")
    if args.environment != "dev":
        raise ReconcileError("environment_must_be_dev")

    public_runtime._require_host()
    project, runtime_root, config_files, env_files = public_runtime._discover_runtime()
    sync = public_runtime._sync_repo(runtime_root, args.expected_sha)

    env = os.environ.copy()
    env["REQSYS_BUILD_SHA"] = args.expected_sha

    bootstrap_base = _compose_base(
        runtime_root,
        project,
        config_files,
        env_files,
        include_overlay=False,
    )
    public_runtime._run(
        bootstrap_base + ["up", "-d", "--no-deps", "--build", "--force-recreate", "api"],
        cwd=runtime_root,
        env=env,
        timeout=900,
    )
    _wait_json(
        LOCAL_API_BASE + "/api/runtime/build-info",
        expected_sha=args.expected_sha,
        timeout_seconds=180,
    )

    vault_name = args.vault_name.strip()
    if not vault_name:
        raise ReconcileError("vault_name_missing")
    client = _secret_client(vault_name)
    adapter_token, producer_token, token_state = _ensure_tokens(
        client,
        os.getenv("COFRE_ADMIN_JWT", "").strip(),
    )

    env["TODO_GLOBAL_ADAPTER_SERVICE_TOKEN"] = adapter_token
    env["TODO_GLOBAL_RUNTIME_TOKEN"] = producer_token
    full_base = _compose_base(
        runtime_root,
        project,
        config_files,
        env_files,
        include_overlay=True,
    )
    public_runtime._run(full_base + ["config", "--quiet"], cwd=runtime_root, env=env, timeout=120)
    public_runtime._run(
        full_base + ["up", "-d", "--build", "reqsys-runtime-redis", "reqsys-runtime", "nginx"],
        cwd=runtime_root,
        env=env,
        timeout=900,
    )

    _wait_json(RUNTIME_BASE + "/health", timeout_seconds=180)
    _wait_json(
        RUNTIME_BASE + "/api/runtime/build-info",
        expected_sha=args.expected_sha,
        timeout_seconds=180,
    )

    unauthorized, _ = _request_json(
        "POST",
        RUNTIME_BASE + "/api/todo-events",
        payload={"schema_version": "invalid"},
    )
    if unauthorized != 401:
        raise ReconcileError(f"todo_runtime_auth_negative_control_failed:http_{unauthorized}")

    e2e = _execute_e2e(args.run_id, args.run_attempt, producer_token)
    evidence = {
        "schema_version": "1.0.0",
        "status": "passed",
        "environment": "dev",
        "host": public_runtime.EXPECTED_HOST,
        "project": project,
        "runtime_sha": args.expected_sha,
        "correlation_id": args.correlation_id,
        "sync": sync,
        "adapter_readiness": True,
        "runtime_health": True,
        "runtime_build_sha_verified": True,
        "auth_negative_control": True,
        "e2e": e2e,
        **token_state,
        "secret_value_exposed": False,
        "production_touched": False,
    }
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--environment", default="dev")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--vault-name", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", default="1")
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        evidence = execute(args)
    except Exception as exc:
        safe = {
            "schema_version": "1.0.0",
            "status": "blocked",
            "environment": "dev",
            "reason": type(exc).__name__,
            "detail": str(exc)[:300],
            "secret_value_exposed": False,
            "production_touched": False,
        }
        args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.write_text(
            json.dumps(safe, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        return 4
    return 0 if evidence.get("status") == "passed" else 4


if __name__ == "__main__":
    raise SystemExit(main())
