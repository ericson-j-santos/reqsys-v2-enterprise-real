from scripts.powerplatform_outlook_connection_probe import _is_outlook_ref


def test_recognizes_office365_connector():
    assert _is_outlook_ref({
        "connectorid": "/providers/Microsoft.PowerApps/apis/shared_office365",
        "connectionreferencelogicalname": "reqsys_outlook",
        "displayname": "Office 365 Outlook",
    })


def test_rejects_unrelated_connector():
    assert not _is_outlook_ref({
        "connectorid": "/providers/Microsoft.PowerApps/apis/shared_planner",
        "connectionreferencelogicalname": "reqsys_planner",
        "displayname": "Planner",
    })
