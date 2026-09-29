import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "graph_official_change_monitor.py"
)
SPEC = importlib.util.spec_from_file_location(
    "graph_official_change_monitor",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def baseline_documents():
    return {
        "channel_list": """
            Permissions
            Delegated (work or school account) ChannelMessage.Read.All
            Group.Read.All, Group.ReadWrite.All
            Application ChannelMessage.Read.Group
            ChannelMessage.Read.All, Group.Read.All, Group.ReadWrite.All
            Note ChannelMessage.Read.Group uses resource-specific consent.
            HTTP request
        """,
        "channel_post": """
            Permissions
            Delegated (work or school account) ChannelMessage.Send Group.ReadWrite.All
            Application Teamwork.Migrate.All Not available
            Application permissions are only supported for migration.
            HTTP request
        """,
        "rsc": """
            Resource-specific consent.
            ChannelMessage.Read.Group Read this team's channel messages. Supported.
            ChannelMessage.Send.Group Send messages to this team's channels. Supported.
        """,
        "permissions_reference": """
            ChannelMessage.Read.All
            Category Application Delegated
            Identifier app-id delegated-id
            AdminConsentRequired Yes Yes
            ChannelMessage.ReadWrite
        """,
        "auth_service": """
            Get access without a user.
            Use the OAuth 2.0 client credentials grant flow.
            grant_type=client_credentials
            scope=https://graph.microsoft.com/.default
        """,
    }


def event_codes(report):
    return {item["code"] for item in report["events"]}


def test_baseline_has_no_material_change():
    report = MODULE.classify_documents(baseline_documents())
    assert report["state"] == "no_material_change"
    assert report["material_change_count"] == 0
    assert report["semantic_observations"]["rsc_read_group"] is True


def test_detects_new_channel_post_permission_surface():
    docs = baseline_documents()
    docs["channel_post"] = docs["channel_post"].replace(
        "Application Teamwork.Migrate.All Not available",
        "Application ChannelMessage.Send.Group, Teamwork.Migrate.All Not available",
    )
    report = MODULE.classify_documents(docs)
    assert report["state"] == "material_change"
    assert "CHANNEL_POST_PERMISSION_SURFACE_CHANGED" in event_codes(report)


def test_read_group_regression_requires_two_official_sources():
    docs = baseline_documents()
    docs["channel_list"] = docs["channel_list"].replace(
        "ChannelMessage.Read.Group",
        "ChannelMessage.Read.All",
    )
    with pytest.raises(MODULE.MonitorContractError):
        MODULE.classify_documents(docs)

    docs["rsc"] = docs["rsc"].replace(
        "ChannelMessage.Read.Group",
        "ChannelMessage.Read.All",
    )
    report = MODULE.classify_documents(docs)
    assert "RSC_READ_GROUP_CHANGED" in event_codes(report)


def test_detects_admin_consent_change():
    docs = baseline_documents()
    docs["permissions_reference"] = docs["permissions_reference"].replace(
        "AdminConsentRequired Yes Yes",
        "AdminConsentRequired No No",
    )
    report = MODULE.classify_documents(docs)
    assert "CHANNELMESSAGE_READ_ALL_ADMIN_CONSENT_CHANGED" in event_codes(report)


def test_detects_auth_deprecation_near_client_credentials():
    docs = baseline_documents()
    docs["auth_service"] += (
        " Client credentials is deprecated for Microsoft Graph in this scenario."
    )
    report = MODULE.classify_documents(docs)
    assert "GRAPH_APP_ONLY_AUTH_CHANGED" in event_codes(report)


def test_missing_auth_contract_fails_closed():
    docs = baseline_documents()
    docs["auth_service"] = "OAuth authentication overview without app-only marker."
    with pytest.raises(MODULE.MonitorContractError):
        MODULE.classify_documents(docs)
