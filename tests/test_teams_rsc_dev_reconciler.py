import importlib.util
import json
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "teams_rsc_dev_reconciler.py"
SPEC = importlib.util.spec_from_file_location("teams_rsc_dev_reconciler", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_probe_ready_on_http_200():
    with mock.patch.object(MODULE, "graph_call", return_value=(200, {"value": []})):
        status, http_status = MODULE.probe_channel("token", "team", "channel")
    assert status == "ready"
    assert http_status == 200


def test_probe_permission_pending_on_http_403():
    with mock.patch.object(MODULE, "graph_call", return_value=(403, {"error": {}})):
        status, http_status = MODULE.probe_channel("token", "team", "channel")
    assert status == "permission_pending"
    assert http_status == 403


def test_install_rsc_uses_only_expected_permission():
    captured = {}

    def fake_call(method, path, token, body=None):
        captured.update({"method": method, "path": path, "body": body})
        return 201, {}

    with mock.patch.object(MODULE, "graph_call", side_effect=fake_call):
        status, http_status = MODULE.install_with_rsc("token", "team-id", "catalog-id")

    assert status == "applied"
    assert http_status == 201
    assert captured["method"] == "POST"
    assert captured["path"] == "/teams/team-id/installedApps"
    permissions = captured["body"]["consentedPermissionSet"]["resourceSpecificPermissions"]
    assert permissions == [
        {"permissionValue": "ChannelMessage.Read.Group", "permissionType": "application"}
    ]


def test_install_forbidden_requests_bootstrap_permission():
    with mock.patch.object(MODULE, "graph_call", return_value=(403, {"error": {}})):
        status, http_status = MODULE.install_with_rsc("token", "team", "catalog")
    assert status == "bootstrap_permission_required"
    assert http_status == 403


def test_state_signature_is_deterministic_and_secret_free():
    payload = {
        "status": "permission_pending",
        "probe_http_status": 403,
        "apply_status": "bootstrap_configuration_missing",
        "apply_http_status": None,
        "team_id": "team",
        "channel_id": "channel",
        "secret": "must-not-be-considered",
    }
    first = MODULE.state_signature(payload)
    second = MODULE.state_signature(dict(payload, secret="different"))
    assert first == second
    assert len(first) == 16


def test_main_does_not_attempt_apply_without_flag(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence.json"
    values = {
        "POWER_PLATFORM_TENANT_ID": "tenant",
        "POWER_PLATFORM_CLIENT_ID": "client",
        "POWER_PLATFORM_CLIENT_SECRET": "secret",
        "PLANNER_TEAMS_DEV_TEAM_ID": "team",
        "PLANNER_TEAMS_DEV_CHANNEL_ID": "channel",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setattr(MODULE, "graph_token", lambda *args: "token")
    monkeypatch.setattr(MODULE, "probe_channel", lambda *args: ("permission_pending", 403))
    with mock.patch.object(MODULE, "install_with_rsc") as install:
        with mock.patch("sys.argv", ["reconciler", "--evidence", str(evidence)]):
            assert MODULE.main() == 0
    install.assert_not_called()
    saved = json.loads(evidence.read_text(encoding="utf-8"))
    assert saved["status"] == "permission_pending"
    assert saved["apply_status"] is None
    assert saved["secret_value_exposed"] is False
