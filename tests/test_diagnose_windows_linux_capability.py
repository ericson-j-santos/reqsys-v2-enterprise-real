from __future__ import annotations

import importlib.util
import pathlib
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
    def Close(self):
        return None


def test_collect_is_read_only_and_never_claims_linux_ready(monkeypatch):
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    monkeypatch.setattr(probe.platform, "system", lambda: "Windows")
    monkeypatch.setattr(probe.platform, "release", lambda: "11")
    monkeypatch.setattr(probe.platform, "machine", lambda: "AMD64")
    checks = {probe.PF_NX_ENABLED: True, probe.PF_SECOND_LEVEL_ADDRESS_TRANSLATION: True,
              probe.PF_VIRT_FIRMWARE_ENABLED: True}
    result = probe.collect(
        expected_host="DESKTOP-PDQK954",
        source_sha=SHA,
        feature_checker=lambda value: checks[value],
        wsl_opener=lambda: FakeKey(),
        wsl_query_info=lambda _key: (2, 0, 0),
    )
    assert result["status"] == "diagnostic_collected"
    assert result["virtualization"]["status"] == "measured"
    assert result["wsl"]["count"] == 2
    assert result["wsl"]["names_collected"] is False
    assert result["wsl_executed"] is False
    assert result["systemd_verified"] is False
    assert result["ready_for_linux_pilot"] is False
    assert result["boot_modified"] is False
    assert result["services_modified"] is False


@pytest.mark.parametrize(
    ("host", "sha", "error"),
    [
        ("OTHER-HOST", SHA, "host_mismatch"),
        ("DESKTOP-PDQK954", "main", "source_sha_invalid"),
        ("bad host!", SHA, "expected_host_invalid"),
    ],
)
def test_identity_and_sha_fail_closed(monkeypatch, host, sha, error):
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    monkeypatch.setattr(probe.platform, "system", lambda: "Windows")
    with pytest.raises(ValueError, match=error):
        probe.collect(expected_host=host, source_sha=sha)


def test_non_windows_is_blocked(monkeypatch):
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    monkeypatch.setattr(probe.platform, "system", lambda: "Linux")
    with pytest.raises(ValueError, match="windows_required"):
        probe.collect(expected_host="DESKTOP-PDQK954", source_sha=SHA)


def test_source_has_no_subprocess_shell_wsl_or_mutating_commands():
    source = FILE.read_text(encoding="utf-8")
    for forbidden in (
        "subprocess", "os.system", "shell=True", "wsl.exe", "systemctl",
        "Enable-WindowsOptionalFeature", "bcdedit", "Restart-Service",
    ):
        assert forbidden not in source
