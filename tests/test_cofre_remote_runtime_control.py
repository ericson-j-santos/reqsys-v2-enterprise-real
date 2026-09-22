from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path("scripts/cofre_remote_runtime_control.py")
SPEC = importlib.util.spec_from_file_location("cofre_remote_runtime_control", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

SHA = "a" * 40


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, *, payload=None, expected=(200,)):
        self.calls.append((method, path, payload, expected))
        if not self.responses:
            raise AssertionError("unexpected request")
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def status_payload(*, sha=SHA, boot="boot-1", env="dev", enabled=True):
    return {
        "environment": env,
        "runtime_target": "pc24x7",
        "runtime_sha": sha,
        "boot_id": boot,
        "self_restart_enabled": enabled,
        "production_touched": False,
        "sensitive_values_exposed": False,
    }


def test_inspect_accepts_only_exact_dev_sha():
    client = FakeClient([status_payload()])
    result = module.inspect_runtime(client, SHA)
    assert result["ok"] is True
    assert result["runtime_sha"] == SHA
    assert result["boot_id"] == "boot-1"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (status_payload(env="prod"), "runtime_environment_not_dev"),
        (status_payload(enabled=False), "self_restart_not_enabled"),
        (status_payload(sha="b" * 40), "runtime_sha_mismatch"),
        ({**status_payload(), "boot_id": ""}, "runtime_boot_id_missing"),
    ],
)
def test_inspect_fails_closed(payload, message):
    client = FakeClient([payload])
    with pytest.raises(module.RemoteControlError, match=message):
        module.inspect_runtime(client, SHA)


def test_restart_binds_confirmation_and_before_boot():
    client = FakeClient(
        [
            status_payload(boot="boot-before"),
            {
                "accepted": True,
                "duplicate": False,
                "runtime_sha": SHA,
                "restart_scheduled": True,
                "production_touched": False,
            },
        ]
    )
    result = module.restart_runtime(client, SHA)
    assert result["before_boot_id"] == "boot-before"
    assert result["restart_scheduled"] is True
    method, path, payload, expected = client.calls[1]
    assert (method, path, expected) == ("POST", "/v1/cofre/runtime/restart", (202,))
    assert payload == {"expected_sha": SHA, "confirm": module.CONFIRM}


def test_verify_requires_boot_change_on_same_sha(monkeypatch):
    client = FakeClient(
        [
            status_payload(boot="boot-before"),
            status_payload(boot="boot-after"),
        ]
    )
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    result = module.verify_restart(client, SHA, "boot-before", 5)
    assert result["ok"] is True
    assert result["boot_id_changed"] is True
    assert result["before_boot_id"] == "boot-before"
    assert result["after_boot_id"] == "boot-after"


def test_verify_does_not_accept_sha_drift(monkeypatch):
    client = FakeClient(
        [
            status_payload(sha="b" * 40, boot="boot-after"),
            status_payload(sha="b" * 40, boot="boot-after-2"),
        ]
    )
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    with pytest.raises(module.RemoteControlError, match="restart_verification_timeout"):
        module.verify_restart(client, SHA, "boot-before", 0)
