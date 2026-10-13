from __future__ import annotations

import json
import subprocess
import sys
from scripts.integration_sql_capture_preflight import (
    initial_evidence,
    record_oidc_outcome,
    resolve_preflight,
)


UPSTREAM_OK = {
    "python_setup": "success",
    "dependencies": "success",
    "contract_tests": "success",
}


def resolve(**overrides):
    values = {
        "mode": "direct_dsn",
        "upstream": UPSTREAM_OK,
        "tenant_configured": True,
        "subscription_configured": True,
        "actual_vault": "kv-reqsys-ccp",
        "expected_vault": "kv-reqsys-ccp",
        "secret_name": "sql-dsn",
        "reader_configured": False,
    }
    values.update(overrides)
    return resolve_preflight(**values)


def test_initial_evidence_exists_before_mode_resolution() -> None:
    assert initial_evidence() == {
        "source": "configuration",
        "status": "preflight_not_run",
        "selection_mode": "explicit",
        "dsn_resolved": False,
        "secret_value_exposed": False,
        "business_data_read": False,
        "production_touched": False,
        "test_touched": False,
    }


def test_install_or_pytest_failure_is_sanitized_and_blocks_all_routes() -> None:
    evidence, outputs = resolve(
        mode="power_platform_gateway",
        upstream={
            "python_setup": "success",
            "dependencies": "failure",
            "contract_tests": "skipped",
        },
    )
    assert evidence["status"] == "upstream_validation_failed"
    assert evidence["upstream"] == {
        "contract_tests": "skipped",
        "dependencies": "failure",
        "python_setup": "success",
    }
    assert outputs["upstream_ready"] == "false"
    assert outputs["preflight_ready"] == "false"
    assert evidence["source"] == "configuration"


def test_missing_or_invalid_mode_fails_before_gateway_selection() -> None:
    missing, missing_outputs = resolve(mode="")
    invalid, invalid_outputs = resolve(mode="gateway")
    assert missing["status"] == "sql_validation_mode_unconfigured"
    assert invalid["status"] == "sql_validation_mode_invalid"
    assert missing_outputs["preflight_ready"] == "false"
    assert invalid_outputs["preflight_ready"] == "false"


def test_gateway_needs_no_reader_dsn_or_vault_and_is_only_deferred() -> None:
    evidence, outputs = resolve(
        mode="power_platform_gateway",
        tenant_configured=False,
        subscription_configured=False,
        actual_vault="",
        expected_vault="kv-reqsys-ccp",
        secret_name="",
        reader_configured=False,
    )
    assert outputs["preflight_ready"] == "true"
    assert outputs["direct_dsn_required"] == "false"
    assert evidence["source"] == "power_platform_gateway"
    assert evidence["status"] == "direct_dsn_not_required"
    assert evidence["dsn_resolved"] is False


def test_direct_mode_blocks_unconfirmed_reader_and_missing_dsn_reference() -> None:
    evidence, outputs = resolve(secret_name="")
    assert outputs["preflight_ready"] == "false"
    assert evidence["status"] == "oidc_configuration_missing"
    assert evidence["configured"]["AZURE_CLIENT_ID_READER_BINDING"] is False
    assert set(evidence["missing_configuration"]) >= {
        "AZURE_CLIENT_ID_READER_BINDING",
        "INTEGRATION_E2E_SQL_DSN_SECRET_NAME",
    }


def test_direct_mode_blocks_wrong_vault_target_without_exposing_values() -> None:
    evidence, outputs = resolve(actual_vault="different-vault", reader_configured=True)
    serialized = json.dumps(evidence)
    assert outputs["preflight_ready"] == "false"
    assert evidence["configured"]["REQSYS_KEY_VAULT_TARGET_MATCH"] is False
    assert "REQSYS_KEY_VAULT_TARGET_MATCH" in evidence["missing_configuration"]
    assert "different-vault" not in serialized
    assert "kv-reqsys-ccp" not in serialized


def test_direct_mode_blocks_invalid_secret_reference() -> None:
    evidence, outputs = resolve(secret_name="invalid/name", reader_configured=True)
    assert outputs["preflight_ready"] == "false"
    assert evidence["status"] == "oidc_configuration_invalid"
    assert evidence["invalid_configuration"] == [
        "INTEGRATION_E2E_SQL_DSN_SECRET_NAME"
    ]


def test_oidc_skipped_and_failure_remain_distinct() -> None:
    ready, _ = resolve(reader_configured=True)
    skipped = record_oidc_outcome(ready, "skipped")
    failed = record_oidc_outcome(ready, "failure")
    assert skipped["status"] == "oidc_login_not_attempted"
    assert failed["status"] == "oidc_login_failed"
    assert skipped["status"] != failed["status"]


def test_unknown_oidc_outcome_never_claims_login_failure_or_success() -> None:
    ready, _ = resolve(reader_configured=True)
    result = record_oidc_outcome(ready, "unknown")
    assert result["status"] == "oidc_outcome_unknown"
    assert result["dsn_resolved"] is False


def test_hostile_mode_is_reduced_to_constant_marker_in_cli_outputs(tmp_path) -> None:
    evidence_path = tmp_path / "source.json"
    github_output = tmp_path / "github-output.txt"
    sentinel = tmp_path / "must-not-exist"
    hostile = f"gateway\\nmode=$(touch {sentinel})\\r$GITHUB_ENV"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/integration_sql_capture_preflight.py",
            "resolve",
            "--output",
            str(evidence_path),
            "--mode",
            hostile,
            "--python-setup-outcome",
            "success",
            "--dependencies-outcome",
            "success",
            "--contract-tests-outcome",
            "success",
            "--github-output",
            str(github_output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    output = github_output.read_text(encoding="utf-8")
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert evidence["status"] == "sql_validation_mode_invalid"
    assert output.splitlines()[0] == "mode=invalid"
    assert hostile not in output
    assert "$(" not in output
    assert not sentinel.exists()
