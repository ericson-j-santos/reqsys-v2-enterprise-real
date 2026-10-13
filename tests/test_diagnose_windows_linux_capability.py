from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import pytest

FILE = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "diagnose_windows_linux_capability.py"
SPEC = importlib.util.spec_from_file_location("windows_linux_capability", FILE)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)

SHA = "a" * 40


class FakeKey:
    def __init__(self):
        self.closed = False

    def Close(self):
        self.closed = True


def _windows(monkeypatch):
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")


class FakeWindowsVersion:
    major = 10
    minor = 0
    build = 26100


def test_collect_is_read_only_and_never_claims_source_or_linux_ready(monkeypatch):
    _windows(monkeypatch)
    checks = {
        probe.PF_NX_ENABLED: True,
        probe.PF_SECOND_LEVEL_ADDRESS_TRANSLATION: True,
        probe.PF_VIRT_FIRMWARE_ENABLED: True,
    }
    result = probe.collect(
        expected_host="DESKTOP-PDQK954",
        requested_source_sha=SHA,
        feature_checker=lambda value: checks[value],
        wsl_opener=lambda: FakeKey(),
        wsl_query_info=lambda _key: (2, 0, 0),
        windows_version_provider=lambda: FakeWindowsVersion(),
        windows_identity=lambda: True,
    )
    assert result["status"] == "diagnostic_collected"
    assert result["requested_source_sha"] == SHA
    assert result["observed_source_sha"] is None
    assert result["source_verified"] is False
    assert result["source_provenance"] == "requested_only"
    assert result["os"] == "Windows"
    assert result["os_release"] == "10.0.26100"
    assert "architecture" not in result
    assert result["wsl"] == {
        "status": "measured",
        "count": 2,
        "reason": "registry_query_succeeded",
        "scope": "current_executor_hkcu",
        "host_wide": False,
        "names_collected": False,
    }
    assert result["wsl_executed"] is False
    assert result["systemd_verified"] is False
    assert result["ready_for_linux_pilot"] is False
    assert result["boot_modified"] is False
    assert result["services_modified"] is False


@pytest.mark.parametrize(
    ("host", "sha", "error"),
    [
        ("OTHER-HOST", SHA, "host_mismatch"),
        ("DESKTOP-PDQK954", "main", "requested_source_sha_invalid"),
        ("bad host!", SHA, "expected_host_invalid"),
    ],
)
def test_identity_and_requested_sha_fail_closed(monkeypatch, host, sha, error):
    _windows(monkeypatch)
    with pytest.raises(ValueError, match=error):
        probe.collect(expected_host=host, requested_source_sha=sha)


def test_valid_but_incorrect_requested_sha_is_not_claimed_as_verified(monkeypatch):
    _windows(monkeypatch)
    requested = "b" * 40
    result = probe.collect(
        expected_host="DESKTOP-PDQK954",
        requested_source_sha=requested,
        feature_checker=lambda _value: True,
        wsl_opener=lambda: FakeKey(),
        wsl_query_info=lambda _key: (0, 0, 0),
        windows_identity=lambda: True,
    )
    assert result["requested_source_sha"] == requested
    assert result["observed_source_sha"] is None
    assert result["source_verified"] is False
    assert result["ready_for_linux_pilot"] is False


def test_missing_registry_key_is_the_only_zero_count_case():
    result = probe.registered_wsl_distribution_count(
        opener=lambda: (_ for _ in ()).throw(FileNotFoundError("absent"))
    )
    assert result["status"] == "measured"
    assert result["count"] == 0
    assert result["reason"] == "registry_key_absent"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (PermissionError(r"C:\Users\private\Lxss"), "registry_access_denied"),
        (OSError(r"C:\Users\private\Lxss"), "registry_open_failed"),
        (ValueError(r"C:\Users\private\Lxss"), "registry_open_invalid"),
    ],
)
def test_registry_open_failures_are_unknown_and_sanitized(exception, reason):
    result = probe.registered_wsl_distribution_count(
        opener=lambda: (_ for _ in ()).throw(exception)
    )
    assert result["status"] == "unknown"
    assert result["count"] is None
    assert result["reason"] == reason
    assert "private" not in str(result)


def test_invalid_registry_query_is_unknown_and_closes_key():
    key = FakeKey()
    result = probe.registered_wsl_distribution_count(
        opener=lambda: key,
        query_info=lambda _key: (_ for _ in ()).throw(ValueError(r"C:\secret\value")),
    )
    assert result["status"] == "unknown"
    assert result["count"] is None
    assert result["reason"] == "registry_data_invalid"
    assert "secret" not in str(result)
    assert key.closed is True


def test_main_never_emits_sensitive_exception_text(monkeypatch, capsys):
    monkeypatch.setattr(
        probe,
        "collect",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError(r"C:\Users\private\token")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["diagnostic", "--expected-host", "DESKTOP-PDQK954", "--requested-source-sha", SHA],
    )
    assert probe.main() == 2
    output = capsys.readouterr().out
    assert "private" not in output
    assert "contract_validation_failed" in output


def test_non_windows_is_blocked(monkeypatch):
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    with pytest.raises(ValueError, match="windows_required"):
        probe.collect(
            expected_host="DESKTOP-PDQK954",
            requested_source_sha=SHA,
            windows_identity=lambda: False,
        )


def test_safe_windows_metadata_omits_optional_release_when_api_fails():
    result = probe._safe_windows_metadata(
        lambda: (_ for _ in ()).throw(OSError(r"C:\\private\\version"))
    )
    assert result == {"os": "Windows"}


def test_real_collector_path_cannot_reach_subprocess_or_shell(monkeypatch):
    _windows(monkeypatch)

    def blocked(*_args, **_kwargs):
        raise AssertionError("shell_or_subprocess_reached")

    monkeypatch.setattr(subprocess, "run", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "check_output", blocked)
    monkeypatch.setattr(probe.os, "system", blocked)
    result = probe.collect(
        expected_host="DESKTOP-PDQK954",
        requested_source_sha=SHA,
        feature_checker=lambda _value: True,
        wsl_opener=lambda: FakeKey(),
        wsl_query_info=lambda _key: (0, 0, 0),
        windows_version_provider=lambda: FakeWindowsVersion(),
        windows_identity=lambda: True,
    )
    assert result["status"] == "diagnostic_collected"
    assert result["source_verified"] is False


def test_source_has_no_subprocess_shell_wsl_or_mutating_commands():
    source = FILE.read_text(encoding="utf-8")
    for forbidden in (
        "import platform",
        "platform.system",
        "platform.release",
        "platform.machine",
        "os.system",
        "shell=True",
        "wsl.exe",
        "systemctl",
        "Enable-WindowsOptionalFeature",
        "bcdedit",
        "Restart-Service",
    ):
        assert forbidden not in source
