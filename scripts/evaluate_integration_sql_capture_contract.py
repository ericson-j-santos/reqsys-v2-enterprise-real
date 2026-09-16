#!/usr/bin/env python3
"""Unified functional gate for the DEV SQL capture path (P1-A).

The Key Vault capture workflow used to demand ``INTEGRATION_E2E_SQL_DSN_SECRET_NAME``
unconditionally, even though the DEV path also supports the
``power_platform_gateway`` validation mode, where no direct DSN exists. This
module unifies the contract:

* ``direct_dsn`` — the legacy behaviour: the Key Vault secret must resolve and
  the procedure contract must be proven against SQL Server.
* ``power_platform_gateway`` — the direct DSN is *not* required and must not be
  requested; connectivity and procedure proof are explicitly deferred to the
  real Power Automate flow E2E, and the deferral is recorded as such instead of
  being reported as a resolved capture.

The gate is fail-closed: an unknown or empty mode blocks, and a gateway run that
silently resolved a DSN also blocks (that would mean the legacy dependency is
still live).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SQL_VALIDATION_DIRECT_DSN = "direct_dsn"
SQL_VALIDATION_POWER_PLATFORM_GATEWAY = "power_platform_gateway"
SUPPORTED_SQL_VALIDATION_MODES = (
    SQL_VALIDATION_DIRECT_DSN,
    SQL_VALIDATION_POWER_PLATFORM_GATEWAY,
)
GATEWAY_SOURCE_STATUS = "direct_dsn_not_required"


def normalize_mode(raw: str | None) -> str:
    return (raw or "").strip().lower()


def direct_dsn_required(mode: str) -> bool:
    return normalize_mode(mode) == SQL_VALIDATION_DIRECT_DSN


def evaluate(
    *,
    mode: str,
    source: dict[str, Any],
    locator: dict[str, Any] | None,
    source_sha: str,
    run_id: str,
    run_attempt: str,
    correlation_id: str,
) -> dict[str, Any]:
    normalized = normalize_mode(mode)
    checks: dict[str, bool] = {}
    blockers: list[str] = []

    if normalized not in SUPPORTED_SQL_VALIDATION_MODES:
        blockers.append(f"sql_validation_mode_invalido:{normalized or 'vazio'}")
        checks["mode_supported"] = False
    else:
        checks["mode_supported"] = True

    dsn_resolved = source.get("dsn_resolved") is True
    source_status = source.get("status")

    if normalized == SQL_VALIDATION_DIRECT_DSN:
        locator_payload = locator or {}
        checks["dsn_resolved"] = dsn_resolved
        checks["source_resolved"] = source_status == "resolved"
        checks["procedure_exists"] = locator_payload.get("procedure_exists") is True
        checks["parameter_contract_ok"] = (
            locator_payload.get("parameter_contract_ok") is True
        )
        checks["locator_resolved"] = locator_payload.get("status") == "resolved"
    elif normalized == SQL_VALIDATION_POWER_PLATFORM_GATEWAY:
        # O segredo legado não pode ser exigido nem consumido neste modo.
        checks["direct_dsn_not_requested"] = source_status == GATEWAY_SOURCE_STATUS
        checks["direct_dsn_absent"] = not dsn_resolved
        checks["locator_deferred"] = locator is None
        if dsn_resolved:
            blockers.append("dependencia_legada_dsn_ainda_ativa")

    blockers.extend(sorted(name for name, passed in checks.items() if not passed))
    blockers = sorted(set(blockers))
    passed = not blockers

    payload: dict[str, Any] = {
        "schema_version": "2.0.0",
        "contract": "integration-sql-capture-unified",
        "feature": "excel_sql_sharepoint_key_vault_capture",
        "sql_validation_mode": normalized,
        "direct_dsn_required": direct_dsn_required(normalized),
        "status": "resolved" if passed else "blocked",
        "gate": "functional_readiness",
        "passed": passed,
        "checks": checks,
        "failed_checks": blockers,
        "source": "azure_key_vault" if direct_dsn_required(normalized) else "power_platform_gateway",
        "source_status": source_status,
        "dsn_resolved": dsn_resolved,
        "source_sha": source_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "correlation_id": correlation_id,
        "secret_value_exposed": False,
        "business_data_read": False,
        "production_touched": False,
        "test_touched": False,
    }
    if normalized == SQL_VALIDATION_DIRECT_DSN:
        locator_payload = locator or {}
        payload.update(
            {
                "procedure": locator_payload.get("procedure"),
                "procedure_exists": locator_payload.get("procedure_exists") is True,
                "parameter_contract_ok": locator_payload.get("parameter_contract_ok")
                is True,
                "locator_error": locator_payload.get("error"),
            }
        )
    else:
        payload.update(
            {
                "connectivity_validation": "deferred_to_real_flow",
                "procedure_validation": "deferred_to_real_flow",
                "deferred_to": "integration-excel-sql-sharepoint-e2e-dev.yml",
            }
        )
    return payload


def _load(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--locator", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-attempt", default="")
    parser.add_argument("--correlation-id", default="")
    args = parser.parse_args()

    source = _load(args.source)
    if source is None:
        raise SystemExit(f"evidencia_de_origem_ausente:{args.source}")

    report = evaluate(
        mode=args.mode,
        source=source,
        locator=_load(args.locator),
        source_sha=args.source_sha,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        correlation_id=args.correlation_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "sql_validation_mode": report["sql_validation_mode"],
                "direct_dsn_required": report["direct_dsn_required"],
                "passed": report["passed"],
                "failed_checks": report["failed_checks"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
