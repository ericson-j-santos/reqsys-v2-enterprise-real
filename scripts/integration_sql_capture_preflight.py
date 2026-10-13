#!/usr/bin/env python3
"""Build sanitized, fail-closed evidence for the DEV SQL capture workflow."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SUPPORTED_MODES = {"direct_dsn", "power_platform_gateway"}
VALID_OUTCOMES = {"success", "failure", "skipped", "cancelled"}
INVALID_MODE_MARKER = "invalid"
EMPTY_MODE_MARKER = "empty"


def _bool(raw: str) -> bool:
    return raw.strip().lower() == "true"


def initial_evidence() -> dict:
    return {
        "source": "configuration",
        "status": "preflight_not_run",
        "selection_mode": "explicit",
        "dsn_resolved": False,
        "secret_value_exposed": False,
        "business_data_read": False,
        "production_touched": False,
        "test_touched": False,
    }


def resolve_preflight(
    *,
    mode: str,
    upstream: dict[str, str],
    tenant_configured: bool,
    subscription_configured: bool,
    actual_vault: str,
    expected_vault: str,
    secret_name: str,
    reader_configured: bool,
) -> tuple[dict, dict[str, str]]:
    raw_mode = mode.strip().lower()
    normalized = (
        raw_mode
        if raw_mode in SUPPORTED_MODES
        else EMPTY_MODE_MARKER
        if not raw_mode
        else INVALID_MODE_MARKER
    )
    evidence = initial_evidence()
    outcomes = {
        name: value if value in VALID_OUTCOMES else "unknown"
        for name, value in sorted(upstream.items())
    }
    upstream_ready = bool(outcomes) and all(value == "success" for value in outcomes.values())
    outputs = {
        "mode": normalized,
        "mode_supported": str(raw_mode in SUPPORTED_MODES).lower(),
        "direct_dsn_required": str(raw_mode == "direct_dsn").lower(),
        "preflight_ready": "false",
        "upstream_ready": str(upstream_ready).lower(),
        "azure_client_id": "",
    }
    if not upstream_ready:
        evidence.update(status="upstream_validation_failed", upstream=outcomes)
        return evidence, outputs
    if raw_mode not in SUPPORTED_MODES:
        evidence["status"] = (
            "sql_validation_mode_unconfigured"
            if normalized == EMPTY_MODE_MARKER
            else "sql_validation_mode_invalid"
        )
        return evidence, outputs
    if raw_mode == "power_platform_gateway":
        evidence.update(
            source="power_platform_gateway",
            status="direct_dsn_not_required",
            selection_mode="gateway_contract",
        )
        outputs["preflight_ready"] = "true"
        return evidence, outputs

    configured = {
        "AZURE_CLIENT_ID_READER_BINDING": reader_configured,
        "AZURE_SUBSCRIPTION_ID": subscription_configured,
        "AZURE_TENANT_ID": tenant_configured,
        "INTEGRATION_E2E_SQL_DSN_SECRET_NAME": bool(secret_name.strip()),
        "REQSYS_KEY_VAULT_NAME": bool(actual_vault.strip()),
        "REQSYS_KEY_VAULT_TARGET_MATCH": (
            bool(actual_vault.strip())
            and bool(expected_vault.strip())
            and actual_vault == expected_vault
        ),
    }
    missing = sorted(name for name, present in configured.items() if not present)
    invalid = []
    if secret_name.strip() and re.fullmatch(r"[A-Za-z0-9-]{1,127}", secret_name.strip()) is None:
        invalid.append("INTEGRATION_E2E_SQL_DSN_SECRET_NAME")
    status = (
        "oidc_configuration_missing"
        if missing
        else "oidc_configuration_invalid"
        if invalid
        else "oidc_configuration_ready"
    )
    evidence.update(
        source="azure_key_vault",
        status=status,
        selection_mode="exact_configured_name",
        configured=configured,
        missing_configuration=missing,
        invalid_configuration=invalid,
    )
    outputs["preflight_ready"] = str(not missing and not invalid).lower()
    return evidence, outputs


def record_oidc_outcome(source: dict, outcome: str) -> dict:
    normalized = outcome.strip().lower()
    result = dict(source)
    if normalized == "failure":
        result.update(status="oidc_login_failed", dsn_resolved=False)
    elif normalized in {"skipped", "cancelled"}:
        result.update(status="oidc_login_not_attempted", dsn_resolved=False)
    elif normalized != "success":
        result.update(status="oidc_outcome_unknown", dsn_resolved=False)
    return result


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--output", required=True, type=Path)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--output", required=True, type=Path)
    resolve.add_argument("--mode", default="")
    resolve.add_argument("--expected-vault", default="")
    resolve.add_argument("--actual-vault", default="")
    resolve.add_argument("--tenant-configured", default="false")
    resolve.add_argument("--subscription-configured", default="false")
    resolve.add_argument("--secret-name", default="")
    resolve.add_argument("--reader-configured", default="false")
    resolve.add_argument("--python-setup-outcome", default="unknown")
    resolve.add_argument("--dependencies-outcome", default="unknown")
    resolve.add_argument("--contract-tests-outcome", default="unknown")
    resolve.add_argument("--github-output", type=Path)
    oidc = sub.add_parser("oidc")
    oidc.add_argument("--output", required=True, type=Path)
    oidc.add_argument("--outcome", required=True)

    args = parser.parse_args()
    if args.command == "init":
        _write(args.output, initial_evidence())
        return 0
    if args.command == "resolve":
        evidence, outputs = resolve_preflight(
            mode=args.mode,
            upstream={
                "python_setup": args.python_setup_outcome,
                "dependencies": args.dependencies_outcome,
                "contract_tests": args.contract_tests_outcome,
            },
            tenant_configured=_bool(args.tenant_configured),
            subscription_configured=_bool(args.subscription_configured),
            actual_vault=args.actual_vault,
            expected_vault=args.expected_vault,
            secret_name=args.secret_name,
            reader_configured=_bool(args.reader_configured),
        )
        _write(args.output, evidence)
        if args.github_output:
            args.github_output.write_text(
                "".join(f"{name}={value}\n" for name, value in outputs.items()),
                encoding="utf-8",
            )
        return 0
    _write(args.output, record_oidc_outcome(_read(args.output), args.outcome))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
