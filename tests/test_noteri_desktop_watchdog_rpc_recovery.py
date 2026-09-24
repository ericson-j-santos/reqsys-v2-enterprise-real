from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "noteri_desktop_watchdog_rpc_recovery.py"
WORKFLOW = ROOT / ".github/workflows/noteri-desktop-watchdog-recovery.yml"

SPEC = importlib.util.spec_from_file_location("noteri_desktop_watchdog_rpc_recovery", SCRIPT)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><BootTrigger><Enabled>true</Enabled></BootTrigger></Triggers>
  <Principals><Principal id="Author"><LogonType>S4U</LogonType></Principal></Principals>
</Task>
"""


def completed(code: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)


def test_recovery_only_queries_and_runs_exact_existing_task(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(m, "schtasks_executable", lambda: Path(r"C:\Windows\System32\schtasks.exe"))

    def fake_run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if "/Query" in argv:
            return completed(0, TASK_XML)
        if "/Run" in argv:
            return completed(0, "SUCCESS")
        raise AssertionError(argv)

    result = m.recover(
        confirm=m.CONFIRM,
        evidence_file=tmp_path / "evidence.json",
        run_cmd=fake_run,
        probe=lambda host, port: True,
        source_host="Noteri",
        platform="nt",
    )
    assert result["ok"] is True
    assert result["run_requested"] is True
    assert result["task_created_or_modified"] is False
    flattened = " ".join(" ".join(call) for call in calls)
    assert "/Query" in flattened and "/Run" in flattened
    assert "/Create" not in flattened and "/Change" not in flattened and "/Delete" not in flattened
    assert all(m.TARGET_HOST in call for call in calls)
    assert all(m.TASK_NAME in call for call in calls)


def test_query_failure_fails_closed_without_run(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(m, "schtasks_executable", lambda: Path(r"C:\Windows\System32\schtasks.exe"))

    def fake_run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return completed(1, stderr="RPC server unavailable")

    result = m.recover(
        confirm=m.CONFIRM,
        evidence_file=tmp_path / "evidence.json",
        run_cmd=fake_run,
        probe=lambda host, port: False,
        source_host="Noteri",
        platform="nt",
    )
    assert result["ok"] is False
    assert result["result"] == "DESKTOP_WATCHDOG_QUERY_BLOCKED"
    assert len(calls) == 1
    assert "/Query" in calls[0]


def test_invalid_task_configuration_is_not_started(tmp_path: Path, monkeypatch) -> None:
    bad_xml = TASK_XML.replace("<LogonType>S4U</LogonType>", "<LogonType>InteractiveToken</LogonType>")
    calls: list[list[str]] = []
    monkeypatch.setattr(m, "schtasks_executable", lambda: Path(r"C:\Windows\System32\schtasks.exe"))

    def fake_run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return completed(0, bad_xml)

    result = m.recover(
        confirm=m.CONFIRM,
        evidence_file=tmp_path / "evidence.json",
        run_cmd=fake_run,
        probe=lambda host, port: True,
        source_host="Noteri",
        platform="nt",
    )
    assert result["result"] == "DESKTOP_WATCHDOG_CONFIGURATION_NOT_READY"
    assert len(calls) == 1


def test_wrong_source_host_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(m.RecoveryError, match="host_origem_nao_autorizado"):
        m.recover(
            confirm=m.CONFIRM,
            evidence_file=tmp_path / "evidence.json",
            source_host="DESKTOP-PDQK954",
            platform="nt",
        )


def test_workflow_is_inputless_noteri_only_and_read_only() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in raw
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert "contents: read" in raw
    assert "contents: write" not in raw
    assert "actions: write" not in raw
    assert "secrets." not in raw
    assert "--confirm" in raw and "RECOVER-DESKTOP-CONTROL-VIA-ORCHESTRATOR" in raw
    assert "persist-credentials: false" in raw
    assert "chatgpt-operational-rules" in raw
    assert "5d1f603241dde37a597d2b7bdc5e07425db7b451" in raw
    assert "session_launcher.py" in raw
    assert "SESSION_LAUNCH_OK" in raw
    assert "state_validated" in raw
    assert "command_gateway.py" in raw
    assert '"--risk", "2"' in raw
    assert '"--expected-head", $env:ANCHOR_SHA' in raw
    assert "DESKTOP_CONTROL_RECOVERY_NOT_CONFIRMED" in raw
    assert "TARGET_REPO: ${{ github.workspace }}" in raw
    assert "path: _target" not in raw
    assert "$recoveryScript = Join-Path $env:TARGET_PATH" in raw
    assert "noteri_desktop_orchestrator_recovery.py" in raw
    assert "C:\\dev\\reqsys-v2-enterprise-real" not in raw
    assert "cancel-in-progress: true" in raw
    assert "host.github_runner.recover.v1" in raw
    assert "host.rdc.recover.v1" in raw
    assert raw.count("shell: powershell") == 4
    assert "shell: pwsh" not in raw
