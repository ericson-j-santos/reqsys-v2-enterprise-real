import pytest

from backend.app.services.integration_profile_provisioning import (
    montar_bundle,
    validar_definicao,
)


def profile_contract():
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


def valid_definition():
    return {
        "triggers": {"Manual": {"type": "Request", "kind": "Button"}},
        "actions": {
            "Excel": {
                "type": "OpenApiConnection",
                "inputs": {
                    "host": {
                        "apiId": "/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness",
                        "connectionName": "shared_excelonlinebusiness",
                    },
                    "parameters": {"CorrelationId": "@guid()"},
                },
            },
            "SQL": {
                "type": "OpenApiConnection",
                "inputs": {
                    "host": {
                        "apiId": "/providers/Microsoft.PowerApps/apis/shared_sql",
                        "connectionName": "shared_sql",
                    }
                },
            },
            "SharePoint": {
                "type": "OpenApiConnection",
                "inputs": {
                    "host": {
                        "apiId": "/providers/Microsoft.PowerApps/apis/shared_sharepointonline",
                        "connectionName": "shared_sharepointonline",
                    }
                },
            },
        },
    }


def valid_payload():
    return {
        "target_environment": "dev",
        "environment_id": "Default-11111111-2222-3333-4444-555555555555",
        "profile_contract": profile_contract(),
        "flow_definition": valid_definition(),
        "connections": {
            "shared_excelonlinebusiness": "excel-connection",
            "shared_sql": "sql-connection",
            "shared_sharepointonline": "sharepoint-connection",
        },
        "display_name": "ReqSys - Excel SQL SharePoint DEV",
        "correlation_id": "corr-1594-test",
    }


def test_accepts_fail_safe_dev_bundle():
    bundle = montar_bundle(valid_payload())
    assert bundle["profile"] == "excel_sql_sharepoint_sync"
    assert bundle["target"]["target_environment"] == "dev"
    assert bundle["flow"]["state"] == "Stopped"
    assert bundle["controls"]["idempotent_by_display_name"] is True
    assert bundle["correlation_id"] == "corr-1594-test"


def test_rejects_non_dev_target():
    payload = valid_payload()
    payload["target_environment"] = "prod"
    with pytest.raises(ValueError, match="restrito a DEV"):
        montar_bundle(payload)


def test_rejects_missing_connection():
    payload = valid_payload()
    del payload["connections"]["shared_sql"]
    with pytest.raises(ValueError, match="Conexões obrigatórias ausentes"):
        montar_bundle(payload)


def test_rejects_unapproved_connector():
    definition = valid_definition()
    definition["actions"]["HTTP"] = {
        "type": "OpenApiConnection",
        "inputs": {
            "host": {
                "apiId": "/providers/Microsoft.PowerApps/apis/shared_http",
                "connectionName": "shared_http",
            }
        },
    }
    errors = validar_definicao(definition)
    assert "conector_nao_permitido:HTTP" in errors


def test_requires_all_three_connectors_to_be_exercised():
    definition = valid_definition()
    del definition["actions"]["SQL"]
    errors = validar_definicao(definition)
    assert "conexao_nao_usada:shared_sql" in errors


def test_requires_correlation_id_in_definition():
    definition = valid_definition()
    definition["actions"]["Excel"]["inputs"]["parameters"] = {}
    errors = validar_definicao(definition)
    assert "correlation_id_ausente" in errors
