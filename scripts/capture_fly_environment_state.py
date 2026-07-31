#!/usr/bin/env python3
"""Capture a sanitized, fail-closed Fly.io environment state snapshot.

The collector reads Fly metadata through flyctl and never persists secret values.
Only secret names and deployment states are retained for promotion decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "infra" / "fly-environments.json"
PASSING_CHECK_STATES = {"passing", "pass", "success", "healthy", "ok"}
DEPLOYED_SECRET_STATES = {"deployed", "complete", "ready", "active"}
REDACTION_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)(token[=:]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password[=:]\s*)[^\s,;]+"),
)


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    payload: Any
    error: str | None
    command: list[str]


def _sanitize_error(value: str | None) -> str | None:
    if not value:
        return None
    sanitized = value[-1000:]
    for pattern in REDACTION_PATTERNS:
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    return sanitized


def run_json_command(command: list[str], timeout_seconds: int = 60) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(False, None, _sanitize_error(str(exc)), command)

    if completed.returncode != 0:
        return CommandResult(
            False,
            None,
            _sanitize_error(completed.stderr or completed.stdout),
            command,
        )
    try:
        payload = json.loads(completed.stdout or "null")
    except json.JSONDecodeError as exc:
        return CommandResult(False, None, f"json_invalid:{type(exc).__name__}", command)
    return CommandResult(True, payload, None, command)


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _as_list(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in (
            "items",
            "Items",
            "machines",
            "Machines",
            "checks",
            "Checks",
            "releases",
            "Releases",
            "secrets",
            "Secrets",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _extract_machine_records(payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            region = _first(value, "region", "Region")
            state = _first(value, "state", "State", "status", "Status")
            machine_id = _first(value, "id", "ID", "machine_id", "MachineID")
            if region is not None and (machine_id is not None or state is not None):
                records.append(
                    {
                        "id": str(machine_id or ""),
                        "region": str(region),
                        "state": str(state or "unknown").lower(),
                    }
                )
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        key = (record["id"], record["region"], record["state"])
        unique[key] = record
    return list(unique.values())


def _normalize_secret_records(payload: Any) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for item in _as_list(payload):
        if not isinstance(item, dict):
            continue
        name = str(_first(item, "name", "Name") or "").strip()
        if not name:
            continue
        state = str(
            _first(
                item,
                "deployment_status",
                "DeploymentStatus",
                "status",
                "Status",
            )
            or "unknown"
        ).strip().lower()
        records.append({"name": name, "deployment_status": state})
    return sorted(records, key=lambda item: item["name"])


def _normalize_checks(payload: Any) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    for item in _as_list(payload):
        if not isinstance(item, dict):
            continue
        name = str(
            _first(item, "name", "Name", "check_name", "CheckName") or "unnamed"
        )
        status = str(
            _first(item, "status", "Status", "state", "State") or "unknown"
        ).lower()
        checks.append({"name": name, "status": status})
    return checks


def _latest_release(payload: Any) -> dict[str, Any] | None:
    releases = [item for item in _as_list(payload) if isinstance(item, dict)]
    if not releases:
        return None
    item = releases[0]
    return {
        "id": _first(item, "id", "ID"),
        "version": _first(item, "version", "Version"),
        "status": _first(item, "status", "Status"),
        "created_at": _first(item, "created_at", "CreatedAt", "createdAt"),
        "description": _first(item, "description", "Description"),
    }


def _critical_config(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    env = payload.get("env") if isinstance(payload.get("env"), dict) else {}
    safe_env_names = sorted(str(key) for key in env)
    safe_env_values = {
        key: env[key]
        for key in (
            "APP_ENV",
            "ALLOW_DEMO_LOGIN",
            "REQSYS_BOOT_FALLBACK",
            "CORS_ORIGINS",
        )
        if key in env
    }
    http_service = (
        payload.get("http_service")
        if isinstance(payload.get("http_service"), dict)
        else {}
    )
    services = payload.get("services") if isinstance(payload.get("services"), list) else []
    mounts = payload.get("mounts") if isinstance(payload.get("mounts"), list) else []
    return {
        "app": payload.get("app"),
        "primary_region": payload.get("primary_region"),
        "env_names": safe_env_names,
        "safe_env_values": safe_env_values,
        "http_service": {
            key: http_service.get(key)
            for key in (
                "internal_port",
                "force_https",
                "auto_start_machines",
                "auto_stop_machines",
                "min_machines_running",
            )
            if key in http_service
        },
        "service_internal_ports": sorted(
            str(item.get("internal_port"))
            for item in services
            if isinstance(item, dict) and item.get("internal_port") is not None
        ),
        "mounts": sorted(
            (
                str(item.get("source") or ""),
                str(item.get("destination") or ""),
            )
            for item in mounts
            if isinstance(item, dict)
        ),
    }


def _config_consistency(
    local_payload: Any,
    remote_payload: Any,
) -> tuple[bool, list[str], dict[str, Any]]:
    local = _critical_config(local_payload)
    remote = _critical_config(remote_payload)
    blockers: list[str] = []
    for key in (
        "app",
        "primary_region",
        "safe_env_values",
        "service_internal_ports",
        "mounts",
    ):
        local_value = local.get(key)
        remote_value = remote.get(key)
        if local_value not in (None, {}, [], "") and local_value != remote_value:
            blockers.append(f"config_mismatch:{key}")
    local_http = local.get("http_service") or {}
    remote_http = remote.get("http_service") or {}
    for key, expected in local_http.items():
        if remote_http.get(key) != expected:
            blockers.append(f"config_mismatch:http_service.{key}")
    return (
        not blockers,
        blockers,
        {
            "local_hash": _canonical_hash(local),
            "remote_hash": _canonical_hash(remote),
            "local": local,
            "remote": remote,
        },
    )


def _app_snapshot(
    *,
    app_name: str,
    config_path: str,
    required_secret_names: Iterable[str],
    min_machines_running: int,
    runner: Callable[[list[str], int], CommandResult],
) -> dict[str, Any]:
    commands = {
        "status": ["flyctl", "status", "--json", "--app", app_name],
        "remote_config": ["flyctl", "config", "show", "--app", app_name],
        "local_config": [
            "flyctl",
            "config",
            "show",
            "--local",
            "--config",
            config_path,
        ],
        "secrets": ["flyctl", "secrets", "list", "--json", "--app", app_name],
        "releases": ["flyctl", "releases", "--json", "--app", app_name],
        "checks": ["flyctl", "checks", "list", "--json", "--app", app_name],
    }
    results = {name: runner(command, 60) for name, command in commands.items()}
    blockers = [
        f"command_failed:{name}" for name, result in results.items() if not result.ok
    ]

    machines = (
        _extract_machine_records(results["status"].payload)
        if results["status"].ok
        else []
    )
    active_machines = [
        machine
        for machine in machines
        if machine["state"] not in {"stopped", "destroyed", "failed", "dead"}
    ]
    if len(active_machines) < min_machines_running:
        blockers.append(
            f"machines_below_minimum:{len(active_machines)}/{min_machines_running}"
        )

    secrets = (
        _normalize_secret_records(results["secrets"].payload)
        if results["secrets"].ok
        else []
    )
    by_name = {item["name"]: item for item in secrets}
    for required in sorted(set(required_secret_names)):
        item = by_name.get(required)
        if item is None:
            blockers.append(f"required_secret_missing:{required}")
        elif item["deployment_status"] not in DEPLOYED_SECRET_STATES:
            blockers.append(
                f"required_secret_not_deployed:{required}:{item['deployment_status']}"
            )

    checks = (
        _normalize_checks(results["checks"].payload)
        if results["checks"].ok
        else []
    )
    for check in checks:
        if check["status"] not in PASSING_CHECK_STATES:
            blockers.append(
                f"health_check_not_passing:{check['name']}:{check['status']}"
            )

    config_consistent = False
    config_evidence: dict[str, Any] = {}
    if results["local_config"].ok and results["remote_config"].ok:
        config_consistent, config_blockers, config_evidence = _config_consistency(
            results["local_config"].payload,
            results["remote_config"].payload,
        )
        blockers.extend(config_blockers)

    command_evidence = {
        name: {
            "ok": result.ok,
            "error": result.error,
            "command": result.command,
        }
        for name, result in results.items()
    }
    return {
        "app": app_name,
        "ready": not blockers,
        "machine_count": len(active_machines),
        "regions": sorted({item["region"] for item in active_machines}),
        "machines": active_machines,
        "required_secret_names": sorted(set(required_secret_names)),
        "secrets": secrets,
        "checks": checks,
        "latest_release": (
            _latest_release(results["releases"].payload)
            if results["releases"].ok
            else None
        ),
        "config_consistent": config_consistent,
        "config_evidence": config_evidence,
        "commands": command_evidence,
        "blocking_issues": sorted(set(blockers)),
    }


def capture_environment(
    *,
    manifest: dict[str, Any],
    environment: str,
    expected_sha: str,
    phase: str,
    runner: Callable[[list[str], int], CommandResult] = run_json_command,
    observed_at_epoch: int | None = None,
) -> dict[str, Any]:
    environments = manifest.get("environments") or {}
    config = environments.get(environment)
    if not isinstance(config, dict):
        raise ValueError(f"environment_not_found:{environment}")
    required_secrets = config.get("required_secret_names") or []
    min_machines = int(config.get("min_machines_running") or 1)
    api = _app_snapshot(
        app_name=str(config["api_app"]),
        config_path=str(config.get("backend_fly_config") or config["fly_config"]),
        required_secret_names=[str(item) for item in required_secrets],
        min_machines_running=min_machines,
        runner=runner,
    )
    frontend = _app_snapshot(
        app_name=str(config["frontend_app"]),
        config_path=str(config["frontend_fly_config"]),
        required_secret_names=[],
        min_machines_running=min_machines,
        runner=runner,
    )
    blockers = [f"api:{item}" for item in api["blocking_issues"]] + [
        f"frontend:{item}" for item in frontend["blocking_issues"]
    ]
    return {
        "schema_version": "1.0.0",
        "contract": "fly-environment-state-capture",
        "generated_at_epoch": int(
            observed_at_epoch if observed_at_epoch is not None else time.time()
        ),
        "environment": environment,
        "phase": phase,
        "expected_sha": expected_sha,
        "ready": not blockers,
        "api": api,
        "frontend": frontend,
        "blocking_issues": blockers,
        "secret_values_persisted": False,
        "production_touched": phase == "post_deploy" and environment == "prod",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture sanitized Fly environment state"
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument(
        "--environment",
        required=True,
        choices=["dev", "hml", "prod"],
    )
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument(
        "--phase",
        choices=["pre_deploy", "post_deploy", "read_only"],
        default="read_only",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    report = capture_environment(
        manifest=manifest,
        environment=args.environment,
        expected_sha=args.expected_sha,
        phase=args.phase,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "environment": args.environment,
                "ready": report["ready"],
                "blocking_issues": report["blocking_issues"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if args.strict and not report["ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
