import json

import pytest

from scripts.integration_excel_sql_sharepoint_dataverse import (
    DataverseFlowError,
    merge_definition,
    normalize_dataverse_url,
    parse_clientdata,
)


def clientdata():
    return json.dumps({
        "properties": {
            "connectionReferences": {
                "shared_excelonlinebusiness": {"connectionName": "excel-private"},
                "shared_sql": {"connectionName": "sql-private"},
                "shared_sharepointonline": {"connectionName": "sp-private"},
            },
            "definition": {"triggers": {"old": {}}, "actions": {"old": {}}},
        }
    })


def definition():
    return {
        "triggers": {"Recorrencia": {"type": "Recurrence"}},
        "actions": {"Listar_linhas": {"type": "OpenApiConnection"}},
    }


def test_merge_preserva_connection_references_e_substitui_so_definition():
    original = parse_clientdata(clientdata())
    merged = json.loads(merge_definition(clientdata(), definition()))
    assert merged["properties"]["connectionReferences"] == original["properties"]["connectionReferences"]
    assert merged["properties"]["definition"] == definition()


def test_rejeita_clientdata_sem_tres_referencias():
    payload = json.loads(clientdata())
    del payload["properties"]["connectionReferences"]["shared_sql"]
    with pytest.raises(DataverseFlowError, match="connection_references_incompletas:shared_sql"):
        parse_clientdata(json.dumps(payload))


def test_normalize_dataverse_url_restringe_https():
    assert normalize_dataverse_url("https://example.crm.dynamics.com/") == "https://example.crm.dynamics.com"
    with pytest.raises(DataverseFlowError, match="dataverse_url_invalida"):
        normalize_dataverse_url("http://example.invalid")
