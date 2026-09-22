import json
from pathlib import Path

import pytest

from scripts.validate_copilot_hitl_dev_import import validate_import_inputs


def _write_valid_settings(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "ConnectionReferences": [
                    {
                        "LogicalName": "reqsys_sharedcommondataserviceforapps",
                        "ConnectionId": "00000000-0000-0000-0000-000000000001",
                        "ConnectorId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                    }
                ],
                "EnvironmentVariables": [
                    {"SchemaName": "reqsys_ApprovalSlaHours", "Value": "24"}
                ],
            }
        ),
        encoding="utf-8",
    )


def test_accepts_governed_dev_import_inputs(tmp_path: Path) -> None:
    package = tmp_path / "ReqSysCopilotHITL_unmanaged.zip"
    package.write_bytes(b"PK-test")
    settings = tmp_path / "deployment-settings.json"
    _write_valid_settings(settings)

    payload = validate_import_inputs(
        package,
        settings,
        "https://reqsys-dev.crm.dynamics.com",
    )

    assert payload["ConnectionReferences"][0]["LogicalName"].startswith("reqsys_")


@pytest.mark.parametrize(
    "environment_url",
    [
        "http://reqsys-dev.crm.dynamics.com",
        "https://reqsys-stg.crm.dynamics.com",
        "https://reqsys-prod.crm.dynamics.com",
        "not-a-url",
    ],
)
def test_blocks_invalid_or_non_dev_environment(tmp_path: Path, environment_url: str) -> None:
    package = tmp_path / "ReqSysCopilotHITL_unmanaged.zip"
    package.write_bytes(b"PK-test")
    settings = tmp_path / "deployment-settings.json"
    _write_valid_settings(settings)

    with pytest.raises(ValueError):
        validate_import_inputs(package, settings, environment_url)


def test_blocks_incomplete_deployment_settings(tmp_path: Path) -> None:
    package = tmp_path / "ReqSysCopilotHITL_unmanaged.zip"
    package.write_bytes(b"PK-test")
    settings = tmp_path / "deployment-settings.json"
    settings.write_text(
        json.dumps(
            {
                "ConnectionReferences": [
                    {
                        "LogicalName": "reqsys_sharedteams",
                        "ConnectionId": "",
                        "ConnectorId": "${CONNECTOR_ID}",
                    }
                ],
                "EnvironmentVariables": [
                    {"SchemaName": "reqsys_TeamsEscalationChannelId", "Value": "TODO"}
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Deployment settings incompleto"):
        validate_import_inputs(
            package,
            settings,
            "https://reqsys-dev.crm.dynamics.com",
        )
