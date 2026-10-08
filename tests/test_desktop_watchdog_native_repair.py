from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repair_desktop_watchdog_native.ps1"


def test_native_watchdog_repair_is_scoped_and_fail_closed() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
    lowered = raw.casefold()

    assert "$ExpectedHost = 'DESKTOP-PDQK954'" in raw
    assert "$WatchdogTask = 'ReqSysDesktopControlPlaneWatchdog'" in raw
    assert "$S4U = 2" in raw
    assert "$RunLevelLimited = 0" in raw
    assert "Schedule.Service" in raw
    assert "RegisterTaskDefinition" in raw
    assert "DesktopWatchdogNativeRepair" in raw
    assert "DESKTOP_WATCHDOG_NATIVE_REPAIRED" in raw
    assert "-Verb RunAs -Wait -PassThru" in raw
    assert "DesktopAdminBroker" not in raw
    assert "ReqSysDesktopAdminBroker" not in raw

    forbidden = (
        "invoke-webrequest",
        "invoke-restmethod",
        "start-bitstransfer",
        "github.com",
        "api.github",
        "winrm",
        "psexec",
        "shutdown.exe",
        "restart-computer",
        "remove-item -recurse",
    )
    for token in forbidden:
        assert token not in lowered


def test_native_watchdog_repair_has_no_user_supplied_parameters() -> None:
    raw = SCRIPT.read_text(encoding="utf-8").casefold()
    assert "param(" not in raw.split("function write-repairevidence", 1)[0]
    assert "$args" not in raw
    assert "read-host" not in raw
    assert "credential" not in raw
