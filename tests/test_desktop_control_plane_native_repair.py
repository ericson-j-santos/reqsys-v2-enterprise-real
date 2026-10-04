from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repair_desktop_control_plane_native.ps1"


def test_native_repair_contract_is_fixed_and_fail_closed() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
    lowered = raw.casefold()

    assert "$ExpectedHost = 'DESKTOP-PDQK954'" in raw
    assert "$BrokerTask = 'ReqSysDesktopAdminBroker'" in raw
    assert "$WatchdogTask = 'ReqSysDesktopControlPlaneWatchdog'" in raw
    assert "$S4U = 2" in raw
    assert "$RunLevelHighest = 1" in raw
    assert "$RunLevelLimited = 0" in raw
    assert "Schedule.Service" in raw
    assert "Start-Process -FilePath 'powershell.exe'" in raw
    assert "-Verb RunAs" in raw
    assert "production_touched" in raw
    assert "secrets_read" in raw
    assert "reboot_performed" in raw
    assert "metadata.json" in raw
    assert "source_sha" in raw
    assert "run.py" in raw

    forbidden = (
        "invoke-webrequest",
        "invoke-restmethod",
        "start-bitstransfer",
        "github.com",
        "api.github",
        "winrm",
        "psexec",
        "wmi",
        "shutdown.exe",
        "restart-computer",
        "remove-item -recurse",
    )
    for token in forbidden:
        assert token not in lowered


def test_native_repair_has_no_user_supplied_parameters() -> None:
    raw = SCRIPT.read_text(encoding="utf-8").casefold()
    assert "param(" not in raw.split("function write-repairevidence", 1)[0]
    assert "$args" not in raw
    assert "read-host" not in raw
    assert "credential" not in raw
