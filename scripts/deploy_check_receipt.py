#!/usr/bin/env python3
"""Build the public, sanitized receipt for the ReqSys DEV deploy-check."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Final

SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
GATEWAY_RESULTS: Final = frozenset({"ok", "blocked"})
INNER_ERROR_CATEGORIES: Final = frozenset(
    {
        "container_cardinality",
        "database_probe_failed",
        "database_probe_invalid",
        "database_probe_timeout",
        "deploy_readiness_timeout",
        "expected_sha_invalid",
        "host_identity_refused",
        "invalid_container_metadata",
        "invalid_image_id",
        "live_identity_invalid",
        "live_liveness_invalid",
        "live_probe_unavailable",
        "live_readiness_invalid",
        "runtime_root_invalid",
        "working_dir_mismatch",
        "compose_identity_mismatch",
    }
)
PROJECT: Final = "wt-pc24x7-piloto"
ENVIRONMENT: Final = "dev"
ISSUE_NUMBER: Final = 2546
TASK_ID: Final = "cwp-cdb85c31e3cc4e972f3094ab"
PUBLIC_KEYS: Final = frozenset(
    {
        "schema_version",
        "result",
        "reason_code",
        "host",
        "environment",
        "source_sha",
        "runtime_sha",
        "correlation_id",
        "issue_number",
        "task_id",
        "database_ok",
        "database_result",
        "gateway_exit_code",
        "gateway_result",
        "command_exit_code",
        "result_verified",
        "session_validated",
        "command_gateway_verified",
        "deploy_performed",
        "runtime_mutated",
        "task_claim_performed",
        "secrets_exposed",
        "production_touched",
    }
)


@dataclass(frozen=True)
class ReceiptContext:
    expected_sha: str
    correlation_id: str
    session_id: str
    host: str


def _exit_code(value: Any) -> int | None:
    if type(value) is not int or not 0 <= value <= 255:
        return None
    return value


def _sha(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.lower()
    return normalized if SHA_RE.fullmatch(normalized) else None


def _object_json(value: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(value, str):
        return None, "inner_result_invalid_type"
    if not value.strip():
        return None, "inner_result_missing"
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None, "inner_result_invalid_json"
    if not isinstance(parsed, dict):
        return None, "inner_result_invalid_type"
    return parsed, None


def _base_receipt(context: ReceiptContext, gateway_exit_code: int | None) -> dict[str, Any]:
    return {
        "schema_version": "2.0.0",
        "result": "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
        "reason_code": "gateway_receipt_invalid",
        "host": context.host,
        "environment": ENVIRONMENT,
        "source_sha": context.expected_sha,
        "runtime_sha": None,
        "correlation_id": context.correlation_id,
        "issue_number": ISSUE_NUMBER,
        "task_id": TASK_ID,
        "database_ok": None,
        "database_result": "unverified",
        "gateway_exit_code": gateway_exit_code,
        "gateway_result": None,
        "command_exit_code": None,
        "result_verified": False,
        "session_validated": True,
        "command_gateway_verified": False,
        "deploy_performed": False,
        "runtime_mutated": False,
        "task_claim_performed": False,
        "secrets_exposed": False,
        "production_touched": False,
    }


def _finish(receipt: dict[str, Any], result: str, reason: str) -> tuple[dict[str, Any], int]:
    receipt["result"] = result
    receipt["reason_code"] = reason
    if set(receipt) != PUBLIC_KEYS:
        raise AssertionError("public receipt key drift")
    return receipt, 0 if result == "REQSYS_DEV_DEPLOY_CHECK_OK" else 1


def build_receipt(
    gateway_text: str,
    gateway_exit_code: Any,
    context: ReceiptContext,
) -> tuple[dict[str, Any], int]:
    """Parse untrusted Gateway output and return only the public allowlisted contract."""
    numeric_gateway_exit = _exit_code(gateway_exit_code)
    receipt = _base_receipt(context, numeric_gateway_exit)
    if numeric_gateway_exit is None:
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "gateway_exit_code_invalid")

    try:
        gateway = json.loads(gateway_text)
    except (TypeError, ValueError):
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "gateway_receipt_invalid")
    if not isinstance(gateway, dict):
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "gateway_receipt_invalid")

    gateway_result = gateway.get("result")
    if gateway_result not in GATEWAY_RESULTS:
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "gateway_result_invalid")
    receipt["gateway_result"] = gateway_result

    command_exit = _exit_code(gateway.get("command_exit_code"))
    if command_exit is None:
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "command_exit_code_invalid")
    receipt["command_exit_code"] = command_exit

    before = gateway.get("before")
    after = gateway.get("after")
    identity_valid = (
        gateway.get("correlation_id") == context.correlation_id
        and gateway.get("session_id") == context.session_id
        and isinstance(before, dict)
        and isinstance(after, dict)
        and before.get("head") == context.expected_sha
        and after.get("head") == context.expected_sha
    )
    if not identity_valid:
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "gateway_identity_mismatch")
    receipt["command_gateway_verified"] = True

    inner, inner_error = _object_json(gateway.get("stdout"))
    if inner_error is not None:
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", inner_error)
    assert inner is not None

    runtime_sha = _sha(inner.get("runtime_sha"))
    database_ok = inner.get("database_ok")
    if runtime_sha is not None:
        receipt["runtime_sha"] = runtime_sha
    if type(database_ok) is bool:
        receipt["database_ok"] = database_ok
        receipt["database_result"] = "passed" if database_ok else "failed"

    success_transport = (
        numeric_gateway_exit == 0 and gateway_result == "ok" and command_exit == 0
    )
    if not success_transport:
        category = inner.get("category")
        if category in INNER_ERROR_CATEGORIES:
            receipt["result_verified"] = True
            return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_FAILED", category)
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "exit_result_mismatch")

    if inner.get("environment") != ENVIRONMENT or inner.get("project") != PROJECT:
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "runtime_identity_mismatch")
    if runtime_sha is None:
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "runtime_sha_invalid")
    if runtime_sha != context.expected_sha:
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "runtime_sha_mismatch")
    if type(database_ok) is not bool:
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED", "database_result_invalid")
    if inner.get("deploy_check_ok") is not True:
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_FAILED", "deploy_check_failed")
    if database_ok is not True:
        receipt["result_verified"] = True
        return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_FAILED", "database_probe_failed")

    receipt["result_verified"] = True
    return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_OK", "ok")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-exit-code", required=True, type=int)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-correlation-id", required=True)
    parser.add_argument("--expected-session-id", required=True)
    parser.add_argument("--host", required=True)
    args = parser.parse_args(argv)
    expected_sha = _sha(args.expected_sha)
    if expected_sha is None:
        parser.error("--expected-sha must be a lowercase 40-character SHA")
    context = ReceiptContext(
        expected_sha=expected_sha,
        correlation_id=args.expected_correlation_id,
        session_id=args.expected_session_id,
        host=args.host,
    )
    receipt, exit_code = build_receipt(
        sys.stdin.read(),
        args.gateway_exit_code,
        context,
    )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
