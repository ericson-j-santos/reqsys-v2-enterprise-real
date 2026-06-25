#!/usr/bin/env python3
"""ReqSys governed schema runtime enforcement.

The enforcer validates payloads at runtime using the governed schema subset used
by the CI schema governance gate. It is framework-agnostic and can be adapted to
FastAPI, Flask, Django, serverless handlers, queues or agents.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.schema_audit import DEFAULT_SCHEMA_RUNTIME_AUDIT, SchemaAuditEvent, SchemaRuntimeAuditSink
from runtime.schema_metrics import DEFAULT_SCHEMA_RUNTIME_METRICS, SchemaRuntimeMetrics
from tools.schema_governance.validate_schema_governance import load_json, validate_value

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "schema-registry.json"


class SchemaRuntimeValidationError(ValueError):
    def __init__(self, message: str, errors: list[str], correlation_id: str) -> None:
        super().__init__(message)
        self.errors = errors
        self.correlation_id = correlation_id


@dataclass(frozen=True)
class RuntimeContract:
    name: str
    version: str
    schema_path: str
    runtime_validation_required: bool


class SchemaRuntimeEnforcer:
    def __init__(
        self,
        registry_path: Path = REGISTRY_PATH,
        metrics: SchemaRuntimeMetrics = DEFAULT_SCHEMA_RUNTIME_METRICS,
        audit: SchemaRuntimeAuditSink = DEFAULT_SCHEMA_RUNTIME_AUDIT,
    ) -> None:
        self.registry_path = registry_path
        self.metrics = metrics
        self.audit = audit
        self.registry = load_json(registry_path)
        self.contracts = self._load_contracts()

    def _load_contracts(self) -> dict[str, RuntimeContract]:
        contracts: dict[str, RuntimeContract] = {}
        schemas = self.registry.get("schemas", [])
        if not isinstance(schemas, list):
            raise ValueError("schema registry must contain a schemas list")
        for item in schemas:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            version = item.get("version")
            schema_path = item.get("schema_path")
            if not all(isinstance(value, str) for value in [name, version, schema_path]):
                continue
            contracts[name] = RuntimeContract(
                name=name,
                version=version,
                schema_path=schema_path,
                runtime_validation_required=item.get("runtime_validation_required") is True,
            )
        return contracts

    def validate(
        self,
        contract_name: str,
        payload: dict[str, Any] | str,
        correlation_id: str | None = None,
        block: bool = True,
    ) -> dict[str, Any]:
        correlation = correlation_id or str(uuid4())
        contract = self.contracts.get(contract_name)
        self.metrics.inc("schema_validation_total")

        if contract is None:
            return self._reject(contract_name, None, correlation, [f"unknown runtime contract: {contract_name}"], block)
        if not contract.runtime_validation_required:
            return self._reject(contract_name, contract.version, correlation, ["runtime validation is not required for this contract"], block)

        value = self._normalize_payload(payload, correlation)
        schema = load_json(ROOT / contract.schema_path)
        schema_version = value.get("schema_version")
        errors = validate_value(value, schema, contract_name)

        if schema_version != contract.version:
            errors.append(f"schema_version mismatch: expected {contract.version}, got {schema_version!r}")
            self.metrics.inc("schema_version_mismatch_total")

        if errors:
            return self._reject(contract.name, contract.version, correlation, errors, block)

        self.metrics.inc("schema_validation_passed_total")
        self.audit.append(
            SchemaAuditEvent(
                correlation_id=correlation,
                contract_name=contract.name,
                schema_version=contract.version,
                valid=True,
                errors=[],
            )
        )
        return {
            "valid": True,
            "correlation_id": correlation,
            "contract_name": contract.name,
            "schema_version": contract.version,
            "errors": [],
        }

    def _normalize_payload(self, payload: dict[str, Any] | str, correlation_id: str) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SchemaRuntimeValidationError("payload is not valid JSON", [str(exc)], correlation_id) from exc
        if not isinstance(value, dict):
            raise SchemaRuntimeValidationError("payload root must be an object", ["payload root must be an object"], correlation_id)
        return value

    def _reject(
        self,
        contract_name: str,
        schema_version: str | None,
        correlation_id: str,
        errors: list[str],
        block: bool,
    ) -> dict[str, Any]:
        self.metrics.inc("schema_validation_failed_total")
        self.metrics.inc("schema_runtime_blocked_payload_total")
        self.audit.append(
            SchemaAuditEvent(
                correlation_id=correlation_id,
                contract_name=contract_name,
                schema_version=schema_version,
                valid=False,
                errors=errors,
            )
        )
        result = {
            "valid": False,
            "correlation_id": correlation_id,
            "contract_name": contract_name,
            "schema_version": schema_version,
            "errors": errors,
        }
        if block:
            raise SchemaRuntimeValidationError("schema runtime validation failed", errors, correlation_id)
        return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate a payload against a governed runtime schema")
    parser.add_argument("contract_name")
    parser.add_argument("payload_path")
    parser.add_argument("--correlation-id", default=None)
    parser.add_argument("--no-block", action="store_true")
    args = parser.parse_args()

    payload_path = Path(args.payload_path)
    payload = load_json(payload_path)
    enforcer = SchemaRuntimeEnforcer()
    try:
        result = enforcer.validate(args.contract_name, payload, correlation_id=args.correlation_id, block=not args.no_block)
    except SchemaRuntimeValidationError as exc:
        print(json.dumps({"valid": False, "correlation_id": exc.correlation_id, "errors": exc.errors}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
