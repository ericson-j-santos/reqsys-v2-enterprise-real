from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "desktop-one-time-reboot-dev.yml"


def _raw() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_one_time_reboot_is_fixed_to_noteri_desktop_and_dev() -> None:
    raw = _raw()
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert "TARGET_HOST: DESKTOP-PDQK954" in raw
    assert 'environment = "dev"' in raw
    assert "owner_remote_host_power_once.py" in raw
    assert "AUTHORIZE-ONE-TIME-REMOTE-REBOOT" in raw
    assert "EXECUTE-ONE-TIME-REMOTE-REBOOT" in raw
    assert "REVOKE-ONE-TIME-REMOTE-REBOOT" in raw


def test_one_time_reboot_is_consumable_and_has_negative_replay_control() -> None:
    raw = _raw()
    assert '"--minutes", "10"' in raw
    assert '"--delay-seconds", "30"' in raw
    assert "REMOTE_REBOOT_REPLAY_WAS_NOT_BLOCKED" in raw
    assert "authorization_consumed = $true" in raw
    assert "replay_blocked = $true" in raw
    assert "authorization_revoked = $true" in raw


def test_one_time_reboot_has_no_arbitrary_inputs_or_production_path() -> None:
    raw = _raw()
    assert "workflow_dispatch:" in raw
    assert "inputs:" not in raw
    assert "${{ inputs." not in raw
    assert '"--target-host", $env:TARGET_HOST' in raw
    assert "arbitrary_target_supported = $false" in raw
    assert "arbitrary_command_supported = $false" in raw
    assert "production_touched = $false" in raw
    assert "shutdown.exe" not in raw
    assert "poweroff" not in raw.casefold()
