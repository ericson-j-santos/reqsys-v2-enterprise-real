import pytest

from scripts.integration_excel_sql_sharepoint_oidc_discovery import (
    OidcDiscoveryError,
    select_flow,
)


def test_select_flow_exige_modern_flow_unico():
    item = {
        "workflowid": "00000000-0000-0000-0000-000000000001",
        "name": "ReqSys - Excel SQL SharePoint DEV E2E",
        "category": 5,
        "type": 1,
    }
    assert select_flow([item], item["name"]) == item


def test_select_flow_rejeita_duplicidade():
    item = {
        "workflowid": "1",
        "name": "ReqSys - Excel SQL SharePoint DEV E2E",
        "category": 5,
        "type": 1,
    }
    with pytest.raises(OidcDiscoveryError, match="dataverse_flow_alvo_ambiguo:2"):
        select_flow([item, dict(item, workflowid="2")], item["name"])


def test_select_flow_ignora_workflow_classico():
    item = {
        "workflowid": "1",
        "name": "ReqSys - Excel SQL SharePoint DEV E2E",
        "category": 0,
        "type": 1,
    }
    with pytest.raises(OidcDiscoveryError, match="dataverse_flow_alvo_ambiguo:0"):
        select_flow([item], item["name"])
