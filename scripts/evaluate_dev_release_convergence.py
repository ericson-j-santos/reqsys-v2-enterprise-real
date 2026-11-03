#!/usr/bin/env python3
"""Decide a convergência DEV sem executar deploy nem inferir aprovação de main."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

SHA = re.compile(r"[0-9a-f]{40}\Z")
RUN_URL = re.compile(
    r"https://github\.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/[1-9][0-9]*\Z"
)
FIELDS = frozenset({
    "schema_version", "environment", "main_sha", "approved_release_sha",
    "approval_run_url", "approval_readback_verified", "observed_sha",
    "observed_at", "signed_locator_verified", "independent_runtime_readback",
    "runtime_kind", "native_runner_ready", "backup_verified",
    "rollback_verified", "deploy_authorized",
})
SAFE_TIMEOUT = timedelta(minutes=15)


class ContractError(ValueError):
    pass


def _time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ContractError("observed_at_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("observed_at_invalid") from exc
    if parsed.tzinfo is None:
        raise ContractError("observed_at_timezone_required")
    return parsed.astimezone(timezone.utc)


def evaluate(data: dict, now: datetime | None = None) -> dict:
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise ContractError("schema_fields_invalid")
    if data["schema_version"] != 1 or data["environment"] != "dev":
        raise ContractError("environment_or_schema_invalid")
    for name in ("main_sha", "approved_release_sha", "observed_sha"):
        if not isinstance(data[name], str) or not SHA.fullmatch(data[name]):
            raise ContractError(f"{name}_invalid")
    if not isinstance(data["approval_run_url"], str) or not RUN_URL.fullmatch(data["approval_run_url"]):
        raise ContractError("approval_run_url_invalid")
    for name in (
        "approval_readback_verified", "signed_locator_verified",
        "independent_runtime_readback", "native_runner_ready",
        "backup_verified", "rollback_verified", "deploy_authorized",
    ):
        if type(data[name]) is not bool:
            raise ContractError(f"{name}_must_be_boolean")
    if data["runtime_kind"] not in ("native", "docker", "unknown"):
        raise ContractError("runtime_kind_invalid")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ContractError("now_timezone_required")
    instant = instant.astimezone(timezone.utc)
    age = instant - _time(data["observed_at"])

    blocked: list[str] = []
    if age > SAFE_TIMEOUT or age < -timedelta(minutes=1):
        blocked.append("runtime_evidence_stale_or_future")
    if not data["approval_readback_verified"]:
        blocked.append("release_approval_unverified")
    if not data["signed_locator_verified"] or not data["independent_runtime_readback"]:
        blocked.append("runtime_readback_unverified")

    desired = data["approved_release_sha"]
    installed = data["observed_sha"]
    if blocked:
        state = "BLOCKED_NO_EVIDENCE"
    elif installed == desired:
        state = "RELEASE_CONVERGED"
    else:
        if data["runtime_kind"] != "native":
            blocked.append("native_deploy_route_required")
        for name, reason in (
            ("native_runner_ready", "native_runner_unavailable"),
            ("backup_verified", "backup_unverified"),
            ("rollback_verified", "rollback_unverified"),
            ("deploy_authorized", "deploy_authorization_missing"),
        ):
            if not data[name]:
                blocked.append(reason)
        state = "READY_FOR_GOVERNED_DEPLOY" if not blocked else "DEPLOY_BLOCKED"
    comparison = {
        "schema_version": 1,
        "environment": "dev",
        "main_sha": data["main_sha"],
        "approved_release_sha": desired,
        "installed_sha": installed,
        "main_ahead_of_approved_release": data["main_sha"] != desired,
        "state": state,
        "blockers": blocked,
        "automatic_deploy": False,
        "production_touched": False,
        "release_effect_verified": state == "RELEASE_CONVERGED",
    }
    fingerprint_fields = {
        key: comparison[key]
        for key in ("environment", "main_sha", "approved_release_sha", "installed_sha", "state", "blockers")
    }
    comparison["fingerprint_sha256"] = sha256(
        json.dumps(fingerprint_fields, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return comparison


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classifica release DEV, sem rede nem deploy")
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate(json.loads(args.evidence_file.read_text(encoding="utf-8")))
    except (ContractError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"DEV_RELEASE_EVIDENCE_BLOCKED:{type(exc).__name__}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"DEV_RELEASE_STATE={result['state']}")
    return 0 if result["state"] == "RELEASE_CONVERGED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
