#!/usr/bin/env python3
"""Build the public, sanitized receipt for the ReqSys DEV deploy-check."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
POST_EXECUTION_RESULTS: Final = frozenset(
    {
        "ok",
        "command_failed",
        "blocked_false_positive_state_change",
        "blocked_unexpected_head_change",
    }
)
INNER_ERROR_CATEGORIES: Final = frozenset(
    {
        "command_failed",
        "compose_identity_mismatch",
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
        "runtime_dependency_missing",
        "runtime_file_missing",
        "runtime_os_error",
        "runtime_payload_invalid",
        "runtime_permission_denied",
        "runtime_subprocess_timeout",
        "working_dir_mismatch",
    }
)
PROJECT: Final = "wt-pc24x7-piloto"
ENVIRONMENT: Final = "dev"
ISSUE_NUMBER: Final = 2546
TASK_ID: Final = "cwp-cdb85c31e3cc4e972f3094ab"
EXIT_COMMAND: Final = 22
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


def _external_exit_code(value: Any) -> int | None:
    if type(value) is not int or not 0 <= value <= 255:
        return None
    return value


def _command_exit_code(value: Any) -> int | None:
    return value if type(value) is int else None


def _sha(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.lower()
    return normalized if SHA_RE.fullmatch(normalized) else None


def _read_redirected_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def _json_object(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _inner_json(value: Any) -> tuple[dict[str, Any] | None, str | None]:
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


def _blocked_receipt(
    stdout_text: str,
    stderr_text: str,
    external_exit: int,
    context: ReceiptContext,
    receipt: dict[str, Any],
) -> tuple[dict[str, Any], int] | None:
    blocked = _json_object(stderr_text)
    if blocked is None or blocked.get("result") != "blocked":
        return None
    if stdout_text.strip():
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "gateway_stream_conflict",
        )
    embedded_exit = _external_exit_code(blocked.get("gateway_exit_code"))
    if (
        blocked.get("correlation_id") != context.correlation_id
        or embedded_exit is None
        or embedded_exit != external_exit
        or external_exit == 0
    ):
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "gateway_blocked_envelope_invalid",
        )
    receipt["gateway_result"] = "blocked"
    return _finish(
        receipt,
        "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
        "gateway_blocked",
    )


def _transport_consistent(
    gateway_result: str,
    external_exit: int,
    embedded_gateway_exit: int,
    command_exit: int,
) -> bool:
    if gateway_result == "ok":
        return external_exit == embedded_gateway_exit == command_exit == 0
    if gateway_result == "command_failed":
        expected_external = (
            command_exit if 1 <= command_exit <= 125 else EXIT_COMMAND
        )
        return (
            command_exit != 0
            and embedded_gateway_exit == command_exit
            and external_exit == expected_external
        )
    return (
        gateway_result
        in {"blocked_false_positive_state_change", "blocked_unexpected_head_change"}
        and external_exit == embedded_gateway_exit
        and embedded_gateway_exit != 0
    )


def build_receipt(
    gateway_stdout: str,
    gateway_stderr: str,
    gateway_exit_code: Any,
    context: ReceiptContext,
) -> tuple[dict[str, Any], int]:
    """Parse untrusted Gateway streams into the public allowlisted contract."""
    external_exit = _external_exit_code(gateway_exit_code)
    receipt = _base_receipt(context, external_exit)
    if external_exit is None:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "gateway_exit_code_invalid",
        )

    blocked_result = _blocked_receipt(
        gateway_stdout,
        gateway_stderr,
        external_exit,
        context,
        receipt,
    )
    if blocked_result is not None:
        return blocked_result
    if gateway_stderr.strip():
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "gateway_stderr_invalid",
        )

    gateway = _json_object(gateway_stdout)
    if gateway is None:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "gateway_receipt_invalid",
        )

    gateway_result = gateway.get("result")
    if not isinstance(gateway_result, str) or gateway_result not in POST_EXECUTION_RESULTS:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "gateway_result_invalid",
        )
    receipt["gateway_result"] = gateway_result

    command_exit = _command_exit_code(gateway.get("command_exit_code"))
    embedded_gateway_exit = _command_exit_code(gateway.get("gateway_exit_code"))
    if command_exit is None:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "command_exit_code_invalid",
        )
    if embedded_gateway_exit is None:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "embedded_gateway_exit_code_invalid",
        )
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
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "gateway_identity_mismatch",
        )
    receipt["command_gateway_verified"] = True

    if not _transport_consistent(
        gateway_result,
        external_exit,
        embedded_gateway_exit,
        command_exit,
    ):
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "exit_result_mismatch",
        )

    inner, inner_error = _inner_json(gateway.get("stdout"))
    if inner_error is not None:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            inner_error,
        )
    assert inner is not None

    runtime_sha = _sha(inner.get("runtime_sha"))
    database_ok = inner.get("database_ok")
    if runtime_sha is not None:
        receipt["runtime_sha"] = runtime_sha
    if type(database_ok) is bool:
        receipt["database_ok"] = database_ok
        receipt["database_result"] = "passed" if database_ok else "failed"

    if gateway_result.startswith("blocked_"):
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "gateway_state_change_blocked",
        )

    if gateway_result == "command_failed":
        category = inner.get("category")
        if inner.get("ok") is not False:
            return _finish(
                receipt,
                "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
                "inner_error_contract_invalid",
            )
        if isinstance(category, str) and category in INNER_ERROR_CATEGORIES:
            receipt["result_verified"] = True
            return _finish(
                receipt,
                "REQSYS_DEV_DEPLOY_CHECK_FAILED",
                category,
            )
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "inner_error_category_invalid",
        )

    if inner.get("environment") != ENVIRONMENT or inner.get("project") != PROJECT:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "runtime_identity_mismatch",
        )
    if runtime_sha is None:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "runtime_sha_invalid",
        )
    if runtime_sha != context.expected_sha:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "runtime_sha_mismatch",
        )
    if type(database_ok) is not bool:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "database_result_invalid",
        )
    deploy_check_ok = inner.get("deploy_check_ok")
    if type(deploy_check_ok) is not bool:
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "deploy_check_result_invalid",
        )
    if deploy_check_ok is False:
        receipt["result_verified"] = True
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_FAILED",
            "deploy_check_failed",
        )
    if database_ok is False:
        receipt["result_verified"] = True
        return _finish(
            receipt,
            "REQSYS_DEV_DEPLOY_CHECK_FAILED",
            "database_probe_failed",
        )

    receipt["result_verified"] = True
    return _finish(receipt, "REQSYS_DEV_DEPLOY_CHECK_OK", "ok")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-exit-code", required=True, type=int)
    parser.add_argument("--gateway-stdout-file", required=True, type=Path)
    parser.add_argument("--gateway-stderr-file", required=True, type=Path)
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
    try:
        stdout_text = _read_redirected_text(args.gateway_stdout_file)
        stderr_text = _read_redirected_text(args.gateway_stderr_file)
    except UnicodeDecodeError:
        receipt, exit_code = _finish(
            _base_receipt(context, _external_exit_code(args.gateway_exit_code)),
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "gateway_stream_encoding_invalid",
        )
    except OSError:
        receipt, exit_code = _finish(
            _base_receipt(context, _external_exit_code(args.gateway_exit_code)),
            "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED",
            "gateway_stream_unavailable",
        )
    else:
        receipt, exit_code = build_receipt(
            stdout_text,
            stderr_text,
            args.gateway_exit_code,
            context,
        )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
