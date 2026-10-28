import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repair_desktop_watchdog_native.ps1"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-desktop-watchdog-recovery.yml"


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


def test_existing_task_repair_is_exact_and_reversible() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
    assert "$TaskUpdate = 4" in raw
    assert "$folder.GetTask($WatchdogTask)" in raw
    assert "Test-ApprovedDrift -Checks $previousChecks" in raw
    assert "-not $Checks.runlevel_limited -and -not $Checks.command_matches" in raw
    assert "$previousDefinition.XmlText" in raw
    assert "$definition.XmlText = $previousXml" in raw
    assert "$action.Path = $Runtime.python" in raw
    assert "$definition.Principal.RunLevel = $RunLevelLimited" in raw
    assert "$folder.RegisterTaskDefinition(" in raw
    assert "$script:RollbackAttempted = $true" in raw
    assert "$script:RollbackVerified" in raw
    assert "WATCHDOG_REPAIR_FAILED_ROLLBACK_ATTEMPTED" in raw
    assert "WATCHDOG_PYTHON_OUTSIDE_LOCALAPPDATA" in raw
    assert "$python = [IO.Path]::GetFullPath([string]$metadata.python_executable)" in raw
    assert "command_matches = $oneAction -and" in raw
    assert "arguments_match = $oneAction -and" in raw
    assert "working_dir_matches = $oneAction -and" in raw
    assert "error = $_.Exception.Message" not in raw
    assert "$script:PrecheckChecks = $previousChecks" in raw
    assert "precheck_checks = $script:PrecheckChecks" in raw
    assert "# Apenas booleanos do contrato" in raw


def test_stage_uses_the_installed_python_with_a_bounded_path() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    stage = raw.split("  stage-watchdog-uac:", 1)[1].split("\n  recover:", 1)[0]
    assert '$python = [IO.Path]::GetFullPath([string]$metadata.python_executable)' in stage
    assert '$python.StartsWith($localRoot, [StringComparison]::OrdinalIgnoreCase)' in stage
    assert '"WATCHDOG_PYTHON_OUTSIDE_LOCALAPPDATA"' in stage
    assert 'task_created_or_modified = $false' in stage
    assert '$version -ne "Python 3.12.10"' in stage


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell COM helper contract")
def test_drift_profile_accepts_only_observed_two_field_difference() -> None:
    functions = SCRIPT.read_text(encoding="utf-8").split("\ntry {\n", 1)[0]
    checks = """
$observed = @{
  enabled=$true; trigger_at_startup=$true; logon_s4u=$true;
  one_exec_action=$true; arguments_match=$true; working_dir_matches=$true;
  runlevel_limited=$false; command_matches=$false
}
if (-not (Test-ApprovedDrift -Checks $observed)) { exit 1 }
$observed.arguments_match = $false
if (Test-ApprovedDrift -Checks $observed) { exit 2 }
$observed.arguments_match = $true
$observed.command_matches = $true
if (Test-ApprovedDrift -Checks $observed) { exit 3 }
if (-not (Test-SamePath -Observed '"C:\\ReqSys\\run.py"' -Expected 'C:\\ReqSys\\run.py')) { exit 4 }
if (Test-SamePath -Observed '"C:\\ReqSys\\run.py" --extra' -Expected 'C:\\ReqSys\\run.py') { exit 5 }
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "-"],
        input=functions + checks, text=True, capture_output=True, timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr


