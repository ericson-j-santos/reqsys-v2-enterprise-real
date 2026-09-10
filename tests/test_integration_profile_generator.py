import json

import pytest

from backend.app.services.integration_profile_generator import (
    IntegrationProfileError,
    generate_artifacts,
    generate_artifacts_json,
    validate_profile,
)


def valid_profile():
    return {
        "profile": "excel_sql_sharepoint_sync",
        "source": {
            "type": "excel",
            "table": "tbEntrada",
            "identifier_column": "Identificador",
            "identifier_pattern": r"^\d+$",
        },
        "sql": {
            "procedure": "integration.usp_ConsultarPorIdentificadores",
            "input_mode": "json",
            "key_field": "Identificador",
        },
        "destination": {
            "type": "sharepoint",
            "list": "ResultadoConsulta",
            "business_key": "ChaveIntegracao",
            "operation": "upsert",
        },
        "governance": {
            "deduplicate": True,
            "correlation_id": True,
            "idempotent": True,
            "quarantine_invalid_rows": True,
        },
    }


def test_accepts_valid_profile():
    validate_profile(valid_profile())


def test_rejects_unsupported_profile():
    payload = valid_profile()
    payload["profile"] = "outro"
    with pytest.raises(IntegrationProfileError, match="Perfil não suportado"):
        validate_profile(payload)


def test_requires_numeric_pattern_to_be_compilable():
    payload = valid_profile()
    payload["source"]["identifier_pattern"] = "["
    with pytest.raises(IntegrationProfileError, match="identifier_pattern"):
        validate_profile(payload)


def test_requires_governance_controls():
    payload = valid_profile()
    payload["governance"]["idempotent"] = False
    with pytest.raises(IntegrationProfileError, match="governance.idempotent"):
        validate_profile(payload)


def test_generates_excel_extractor_using_only_identifier_column():
    artifacts = generate_artifacts(valid_profile())
    script = artifacts.office_script
    assert 'getName() === "tbEntrada"' in script
    assert 'getName() === "Identificador"' in script
    assert "new Set<string>()" in script
    assert "identifiers.add(value)" in script


def test_generates_parameterized_openjson_sql_template():
    artifacts = generate_artifacts(valid_profile())
    sql = artifacts.sql_procedure_template
    assert "@IdsJson NVARCHAR(MAX)" in sql
    assert "@CorrelationId UNIQUEIDENTIFIER" in sql
    assert "OPENJSON(@IdsJson)" in sql
    assert "LIKE '%[^0-9]%'" in sql
    assert "IN (" not in sql


def test_generates_sharepoint_upsert_contract_with_independent_read():
    contract = generate_artifacts(valid_profile()).power_automate_contract
    assert contract["sharepoint"]["operation"] == "upsert"
    assert contract["sharepoint"]["business_key"] == "ChaveIntegracao"
    assert contract["controls"]["idempotent"] is True
    assert contract["controls"]["independent_final_read"] is True
    assert "verify_sharepoint_persistence" in contract["steps"]


def test_json_output_is_serializable_and_keeps_profile():
    output = json.loads(generate_artifacts_json(valid_profile()))
    assert output["profile"] == "excel_sql_sharepoint_sync"
    assert output["power_automate_contract"]["controls"]["correlation_id"] is True
