"""Contract tests for the unified DEV SQL capture gate (P1-A)."""

from __future__ import annotations

from pathlib import Path

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
    assert report["deferred_to"] == "integration-excel-sql-sharepoint-e2e-dev.yml"


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


def test_workflow_gates_the_legacy_secret_behind_the_mode() -> None:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["capture"]["steps"]
    by_name = {str(step.get("name", "")): step for step in steps}

    dsn_step = next(
        step for name, step in by_name.items() if "Capturar DSN" in name
    )
    assert "steps.sql-mode.outputs.direct_dsn_required == 'true'" in dsn_step["if"]

    locator_step = next(
        step for name, step in by_name.items() if "Validar procedure" in name
    )
    assert locator_step["if"] == "steps.sql-mode.outputs.direct_dsn_required == 'true'"

    gateway_step = next(
        step for name, step in by_name.items() if "dispensa do DSN" in name
    )
    assert gateway_step["if"] == "steps.sql-mode.outputs.direct_dsn_required != 'true'"
    assert GATEWAY_SOURCE_STATUS in gateway_step["run"]


def test_workflow_defaults_to_direct_dsn_mode() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "INTEGRATION_E2E_SQL_VALIDATION_MODE" in raw
    assert "|| 'direct_dsn'" in raw
