#!/usr/bin/env python3
"""Self-contained tests for ReqSys schema runtime enforcement."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from runtime.schema_audit import SchemaRuntimeAuditSink  # noqa: E402
from runtime.schema_metrics import SchemaRuntimeMetrics  # noqa: E402
from runtime.schema_runtime_enforcer import SchemaRuntimeEnforcer, SchemaRuntimeValidationError  # noqa: E402
from tools.schema_governance.validate_schema_governance import load_json  # noqa: E402

VALID_PAYLOAD = ROOT / "examples" / "runtime" / "product-intelligence-event.runtime.valid.json"
INVALID_VERSION_PAYLOAD = ROOT / "examples" / "runtime" / "product-intelligence-event.runtime.invalid-version.json"
INVALID_EXTRA_FIELD_PAYLOAD = ROOT / "examples" / "runtime" / "product-intelligence-event.runtime.invalid-extra-field.json"


def new_enforcer() -> SchemaRuntimeEnforcer:
    return SchemaRuntimeEnforcer(metrics=SchemaRuntimeMetrics(), audit=SchemaRuntimeAuditSink())


def assert_raises_validation(fn) -> SchemaRuntimeValidationError:
    try:
        fn()
    except SchemaRuntimeValidationError as exc:
        return exc
    raise AssertionError("SchemaRuntimeValidationError was not raised")


def test_valid_payload_passes_and_emits_metrics() -> None:
    enforcer = new_enforcer()
    payload = load_json(VALID_PAYLOAD)

    result = enforcer.validate("product-intelligence-event", payload, correlation_id="runtime-test-valid")

    assert result["valid"] is True
    assert result["correlation_id"] == "runtime-test-valid"
    assert enforcer.metrics.snapshot()["schema_validation_passed_total"] == 1
    assert enforcer.audit.snapshot()[0]["valid"] is True


def test_invalid_schema_version_is_blocked() -> None:
    enforcer = new_enforcer()
    payload = load_json(INVALID_VERSION_PAYLOAD)

    exc = assert_raises_validation(lambda: enforcer.validate("product-intelligence-event", payload, correlation_id="runtime-test-version"))

    assert "runtime-test-version" == exc.correlation_id
    assert any("schema_version" in error for error in exc.errors)
    metrics = enforcer.metrics.snapshot()
    assert metrics["schema_validation_failed_total"] == 1
    assert metrics["schema_version_mismatch_total"] == 1
    assert metrics["schema_runtime_blocked_payload_total"] == 1


def test_extra_field_is_blocked() -> None:
    enforcer = new_enforcer()
    payload = load_json(INVALID_EXTRA_FIELD_PAYLOAD)

    exc = assert_raises_validation(lambda: enforcer.validate("product-intelligence-event", payload, correlation_id="runtime-test-extra"))

    assert any("additional property" in error for error in exc.errors)
    assert enforcer.audit.snapshot()[0]["valid"] is False


def test_unknown_contract_is_blocked() -> None:
    enforcer = new_enforcer()
    payload = load_json(VALID_PAYLOAD)

    exc = assert_raises_validation(lambda: enforcer.validate("unknown-contract", payload, correlation_id="runtime-test-unknown"))

    assert any("unknown runtime contract" in error for error in exc.errors)


def test_no_block_mode_returns_invalid_result() -> None:
    enforcer = new_enforcer()
    payload = load_json(INVALID_EXTRA_FIELD_PAYLOAD)

    result = enforcer.validate("product-intelligence-event", payload, correlation_id="runtime-test-no-block", block=False)

    assert result["valid"] is False
    assert result["correlation_id"] == "runtime-test-no-block"
    assert result["errors"]


def run() -> int:
    tests = [
        test_valid_payload_passes_and_emits_metrics,
        test_invalid_schema_version_is_blocked,
        test_extra_field_is_blocked,
        test_unknown_contract_is_blocked,
        test_no_block_mode_returns_invalid_result,
    ]
    failures: list[str] = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failures.append(f"{test.__name__}: {exc}")
            print(f"FAIL {test.__name__}: {exc}", file=sys.stderr)
    if failures:
        print("Schema runtime enforcement tests failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Schema runtime enforcement tests passed: {len(tests)} tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
