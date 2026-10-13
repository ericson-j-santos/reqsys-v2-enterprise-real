"""Contract tests for the unified DEV SQL capture gate (P1-A)."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

import pytest
import yaml

from scripts.evaluate_integration_sql_capture_contract import (
    GATEWAY_SOURCE_STATUS,
    SUPPORTED_SQL_VALIDATION_MODES,
    direct_dsn_required,
    evaluate,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "integration-excel-sql-sharepoint-key-vault-capture-dev.yml"
)

RUN_CONTEXT = {
    "source_sha": "c" * 40,
    "run_id": "1234",
    "run_attempt": "1",
    "correlation_id": "kv-sql-capture-1234-1",
}


def gateway_source() -> dict:
    return {
        "source": "power_platform_gateway",
        "status": GATEWAY_SOURCE_STATUS,
        "dsn_resolved": False,
    }


def direct_source() -> dict:
    return {"source": "azure_key_vault", "status": "resolved", "dsn_resolved": True}


def direct_locator() -> dict:
    return {
        "status": "resolved",
        "procedure": "integration.usp_ConsultarPorIdentificadores",
        "procedure_exists": True,
        "parameter_contract_ok": True,
        "error": None,
    }


# --- modo gateway: sem dependência do segredo legado -------------------------


def test_gateway_mode_does_not_require_the_legacy_dsn_secret() -> None:
    report = evaluate(
        mode="power_platform_gateway",
        source=gateway_source(),
        locator=None,
        **RUN_CONTEXT,
    )

    assert report["passed"] is True, report["failed_checks"]
    assert report["direct_dsn_required"] is False
    assert report["dsn_resolved"] is False
    assert report["connectivity_validation"] == "deferred_to_real_flow"
    assert report["procedure_validation"] == "deferred_to_real_flow"
    assert report["deferred_to"] == "integration-excel-sql-sharepoint-oidc-dev.yml"


def test_gateway_mode_blocks_when_legacy_dsn_is_still_consumed() -> None:
    """Resolver um DSN em modo gateway significa dependência legada ativa."""
    report = evaluate(
        mode="power_platform_gateway",
        source={"status": "resolved", "dsn_resolved": True},
        locator=None,
        **RUN_CONTEXT,
    )

    assert report["passed"] is False
    assert "dependencia_legada_dsn_ainda_ativa" in report["failed_checks"]


def test_gateway_mode_blocks_when_source_evidence_is_from_key_vault() -> None:
    report = evaluate(
        mode="power_platform_gateway",
        source={"status": "secret_name_unconfigured", "dsn_resolved": False},
        locator=None,
        **RUN_CONTEXT,
    )

    assert report["passed"] is False
    assert "direct_dsn_not_requested" in report["failed_checks"]


# --- modo direct_dsn: contrato legado preservado -----------------------------


def test_direct_dsn_mode_still_requires_full_proof() -> None:
    report = evaluate(
        mode="direct_dsn",
        source=direct_source(),
        locator=direct_locator(),
        **RUN_CONTEXT,
    )

    assert report["passed"] is True, report["failed_checks"]
    assert report["direct_dsn_required"] is True
    assert report["procedure_exists"] is True


@pytest.mark.parametrize(
    ("source", "locator", "expected"),
    [
        (
            {"status": "secret_name_unconfigured", "dsn_resolved": False},
            direct_locator(),
            "dsn_resolved",
        ),
        (
            direct_source(),
            {"status": "resolved", "procedure_exists": False, "parameter_contract_ok": True},
            "procedure_exists",
        ),
        (
            direct_source(),
            {"status": "resolved", "procedure_exists": True, "parameter_contract_ok": False},
            "parameter_contract_ok",
        ),
        (direct_source(), None, "locator_resolved"),
    ],
)
def test_direct_dsn_mode_fails_closed(source, locator, expected) -> None:
    report = evaluate(mode="direct_dsn", source=source, locator=locator, **RUN_CONTEXT)

    assert report["passed"] is False
    assert expected in report["failed_checks"]


# --- modo inválido -----------------------------------------------------------


@pytest.mark.parametrize("mode", ["", "   ", "gateway", "dsn"])
def test_unknown_mode_blocks(mode: str) -> None:
    report = evaluate(
        mode=mode, source=gateway_source(), locator=None, **RUN_CONTEXT
    )

    assert report["passed"] is False
    assert any(
        item.startswith("sql_validation_mode_invalido")
        for item in report["failed_checks"]
    )


def test_supported_modes_match_the_readiness_contract() -> None:
    """Os dois caminhos DEV precisam falar exatamente o mesmo vocabulário.

    A leitura é estática (``ast``) para não arrastar dependências de runtime do
    readiness (httpx) para dentro deste contrato.
    """
    import ast

    module = ROOT / "scripts" / "integration_excel_sql_sharepoint_readiness.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    constants = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    readiness_modes = {
        constants["SQL_VALIDATION_DIRECT_DSN"],
        constants["SQL_VALIDATION_POWER_PLATFORM_GATEWAY"],
    }

    assert set(SUPPORTED_SQL_VALIDATION_MODES) == readiness_modes


def test_direct_dsn_required_helper() -> None:
    assert direct_dsn_required("direct_dsn") is True
    assert direct_dsn_required("DIRECT_DSN") is True
    assert direct_dsn_required("power_platform_gateway") is False


# --- contrato do workflow ----------------------------------------------------


def test_workflow_resolves_explicit_mode_before_any_oidc_step() -> None:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["capture"]["steps"]
    names = [str(step.get("name", "")) for step in steps]

    resolver = names.index("Resolver modo e atualizar evidência sanitizada")
    login = names.index("Login Azure OIDC com identidade reader Key Vault DEV")
    capture = names.index("Capturar DSN sem expor nome ou valor")
    locator = names.index("Validar procedure e contrato SQL")
    assert resolver < login < capture < locator

    by_name = {str(step.get("name", "")): step for step in steps}
    assert "preflight_ready == 'true'" in by_name[names[login]]["if"]
    assert "azure-login.outcome == 'success'" in by_name[names[capture]]["if"]
    assert "key-vault.outputs.dsn_resolved == 'true'" in by_name[names[locator]]["if"]


def test_workflow_has_no_implicit_mode_or_retired_or_mutator_identity() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "INTEGRATION_E2E_SQL_VALIDATION_MODE" in raw
    assert "|| 'direct_dsn'" not in raw
    assert "CCP_AZURE_CLIENT_ID_FLY_GOVERNED_COMMAND" not in raw
    assert "vars.CCP_AZURE_CLIENT_ID }}" not in raw
    assert "--reader-configured false" in raw


def test_workflow_gateway_path_never_calls_azure_key_vault_or_sql() -> None:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["capture"]["steps"]
    guarded = [
        step
        for step in steps
        if any(
            token in str(step.get("name", ""))
            for token in ("Login Azure", "Capturar DSN", "Validar procedure")
        )
    ]

    assert guarded
    for step in guarded:
        condition = str(step.get("if", ""))
        assert "steps.sql-mode.outputs.direct_dsn_required == 'true'" in condition


def test_workflow_always_materializes_and_publishes_sanitized_evidence() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    document = yaml.safe_load(raw)
    steps = document["jobs"]["capture"]["steps"]
    by_name = {str(step.get("name", "")): step for step in steps}

    names = [str(step.get("name", "")) for step in steps]
    initializer = by_name["Inicializar evidência sanitizada antes de passos falíveis"]
    resolver = by_name["Resolver modo e atualizar evidência sanitizada"]
    assert names.index("Inicializar evidência sanitizada antes de passos falíveis") < names.index("Instalar dependências mínimas")
    assert "integration_sql_capture_preflight.py init" in initializer["run"]
    assert resolver["if"] == "always()"
    assert "integration_sql_capture_preflight.py resolve" in resolver["run"]
    assert "--python-setup-outcome" in resolver["run"]
    assert "--contract-tests-outcome" in resolver["run"]
    assert "--expected-vault" in resolver["run"]

    consolidated = by_name["Gerar evidência consolidada sanitizada"]
    published = by_name["Publicar evidência sanitizada"]
    gate = by_name["Gate funcional obrigatório antes do verde"]
    assert consolidated["if"] == "always()"
    assert published["if"] == "always()"
    assert gate["if"] == "always()"


@pytest.mark.parametrize(
    ("status", "source_category"),
    [
        ("oidc_configuration_missing", "azure_key_vault"),
        ("oidc_login_failed", "azure_key_vault"),
    ],
)
def test_direct_failures_preserve_origin_and_never_turn_green(
    status: str, source_category: str
) -> None:
    report = evaluate(
        mode="direct_dsn",
        source={
            "source": source_category,
            "status": status,
            "dsn_resolved": False,
        },
        locator=None,
        **RUN_CONTEXT,
    )

    assert report["passed"] is False
    assert report["source"] == source_category
    assert report["source_status"] == status
    assert "dsn_resolved" in report["failed_checks"]
    assert "source_resolved" in report["failed_checks"]


@pytest.mark.parametrize("mode", ["", "unknown"])
def test_invalid_mode_preserves_configuration_category(mode: str) -> None:
    report = evaluate(
        mode=mode,
        source={
            "source": "configuration",
            "status": (
                "sql_validation_mode_unconfigured"
                if not mode
                else "sql_validation_mode_invalid"
            ),
            "dsn_resolved": False,
        },
        locator=None,
        **RUN_CONTEXT,
    )

    assert report["passed"] is False
    assert report["source"] == "configuration"
    assert report["source_status"].startswith("sql_validation_mode_")


def test_cli_materializes_sanitized_summary_when_source_is_missing(tmp_path) -> None:
    missing = tmp_path / "private-location" / "source.json"
    output = tmp_path / "capture-summary.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "evaluate_integration_sql_capture_contract.py"),
            "--mode",
            "direct_dsn",
            "--source",
            str(missing),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(report)
    assert completed.returncode == 1
    assert report["passed"] is False
    assert report["source_status"] == "source_evidence_missing"
    assert "source_evidence_missing" in report["failed_checks"]
    assert str(missing) not in serialized
    assert str(missing) not in completed.stdout
    assert str(missing) not in completed.stderr


def test_upstream_failure_remains_blocked_by_evaluator() -> None:
    from scripts.integration_sql_capture_preflight import resolve_preflight

    source, outputs = resolve_preflight(
        mode="power_platform_gateway",
        upstream={
            "python_setup": "success",
            "dependencies": "failure",
            "contract_tests": "skipped",
        },
        tenant_configured=False,
        subscription_configured=False,
        actual_vault="",
        expected_vault="kv-reqsys-ccp",
        secret_name="",
        reader_configured=False,
    )
    report = evaluate(
        mode=outputs["mode"], source=source, locator=None, **RUN_CONTEXT
    )

    assert source["status"] == "upstream_validation_failed"
    assert report["passed"] is False
    assert "direct_dsn_not_requested" in report["failed_checks"]


def test_workflow_passes_mode_to_consolidation_through_environment() -> None:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["capture"]["steps"]
    consolidated = next(
        step
        for step in steps
        if step.get("name") == "Gerar evidência consolidada sanitizada"
    )

    assert consolidated["env"]["SQL_VALIDATION_MODE"] == "${{ steps.sql-mode.outputs.mode }}"
    assert consolidated["env"]["DSN_RESOLVED"] == "${{ steps.key-vault.outputs.dsn_resolved }}"
    assert '--mode "$SQL_VALIDATION_MODE"' in consolidated["run"]
    assert '${{ steps.sql-mode.outputs.mode }}' not in consolidated["run"]
    assert '${{ steps.key-vault.outputs.dsn_resolved }}' not in consolidated["run"]
