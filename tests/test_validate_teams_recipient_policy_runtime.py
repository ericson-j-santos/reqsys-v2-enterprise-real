import json
from datetime import UTC, datetime

from scripts.validate_teams_recipient_policy_runtime import (
    DYNAMIC_PATH,
    LEGACY_PATH,
    build_report,
    evaluate_paths,
)


def test_dynamic_and_legacy_routes_are_ready():
    result = evaluate_paths({DYNAMIC_PATH: {"post": {}}, LEGACY_PATH: {"post": {}}})

    assert result["migration_state"] == "dynamic_ready"
    assert result["result"] == "passed"
    assert result["dynamic_available"] is True
    assert result["legacy_available"] is True


def test_legacy_only_requires_controlled_fallback():
    result = evaluate_paths({LEGACY_PATH: {"post": {}}})

    assert result["migration_state"] == "legacy_fallback_required"
    assert result["result"] == "advisory"
    assert result["dynamic_available"] is False
    assert result["legacy_available"] is True


def test_missing_routes_fails_readiness():
    result = evaluate_paths({"/health": {"get": {}}})

    assert result["migration_state"] == "gateway_route_unavailable"
    assert result["result"] == "failed"


def test_report_is_deterministic_and_never_claims_production_mutation():
    now = datetime(2026, 7, 30, 19, 0, tzinfo=UTC)
    document = {"paths": {LEGACY_PATH: {"post": {}}}}

    first = build_report("https://reqsys-api.fly.dev/", document, now)
    second = build_report("https://reqsys-api.fly.dev/", document, now)

    assert first == second
    assert first["production_touched"] is False
    assert first["base_url"] == "https://reqsys-api.fly.dev"
    assert len(first["evidence_sha256"]) == 64
    json.dumps(first)
