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


def test_workflow_modes_are_bounded_governed_and_read_only() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    # Superfície única e explicitamente limitada: nenhum input livre além do modo.
    assert "workflow_dispatch:" in raw
    assert "mode:" in raw
    assert "type: choice" in raw
    assert "default: watchdog" in raw
    for mode in ("watchdog", "runner-recover", "runner-bootstrap", "runner-canary", "alm-runner-bootstrap", "reboot-once"):
        assert f"- {mode}" in raw
    assert raw.count("description: 'Bounded recovery mode'") == 1

    # Permissões e invariantes comuns permanecem somente leitura/fail-closed.
    assert "contents: read" in raw
    assert "contents: write" not in raw
    assert "actions: write" not in raw
    assert "secrets." not in raw
    assert "persist-credentials: false" in raw
    assert "chatgpt-operational-rules" in raw
    assert "session_launcher.py" in raw
    assert "SESSION_LAUNCH_OK" in raw
    assert "state_validated" in raw
    assert "command_gateway.py" in raw
    assert '"--risk", "2"' in raw
    assert '"--expected-head", $env:ANCHOR_SHA' in raw
    assert "TARGET_REPO: ${{ github.workspace }}" in raw
    assert "path: _target" not in raw
    assert "C:\\dev\\reqsys-v2-enterprise-real" not in raw
    assert "shell: pwsh" not in raw
    assert "actions/checkout@v4" not in raw
    assert "actions/upload-artifact@v4" not in raw
    assert raw.count("actions/checkout@11d5960a326750d5838078e36cf38b85af677262") == 12
    assert "actions/setup-python@" not in raw
    assert "Get-Command python" not in raw
    assert raw.count("Prepare pinned portable Python 3.12") == 6
    assert raw.count("python-3.12.10-embed-amd64.zip") == 6
    assert raw.count("4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3") == 6
    assert raw.count("Get-FileHash -LiteralPath $zip -Algorithm SHA256") == 6
    assert raw.count("REQSYS_PYTHON=$python") == 6
    assert raw.count("python312._pth") == 6
    assert raw.count("$rulesScripts = Join-Path $env:GITHUB_WORKSPACE") == 6
    assert raw.count("PORTABLE_PYTHON_PTH_MISSING") == 6
    assert raw.count("--require-runner-version-preflight") == 5
    assert raw.count("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02") == 6

    # Modo watchdog legado continua restrito ao Noteri e à tarefa fixa existente.
    assert "if: ${{ inputs.mode == 'watchdog' || inputs.mode == '' }}" in raw
    assert "RUN-EXISTING-DESKTOP-WATCHDOG" in raw
    assert "DESKTOP_WATCHDOG_RECOVERY_NOT_CONFIRMED" in raw
    assert "$recoveryScript = Join-Path $env:TARGET_PATH" in raw
    assert "noteri_desktop_watchdog_rpc_recovery.py" in raw

    # Reboot one-shot usa a exceção canônica separada e consumível, somente no Noteri.
    assert "reboot-once:" in raw
    assert "if: ${{ inputs.mode == 'reboot-once' }}" in raw
    assert "owner_remote_host_power_once.py" in raw
    assert "REMOTE_REBOOT_REPLAY_WAS_NOT_BLOCKED" in raw
    assert "authorization_revoked = $true" in raw

    # Recovery direto reutiliza o contrato permanente já instalado, sem bootstrap.
    assert "runner-recover:" in raw
    assert "if: ${{ inputs.mode == 'runner-recover' }}" in raw
    assert "noteri_desktop_orchestrator_runner_recovery.py" in raw
    assert "RECOVER-DESKTOP-GITHUB-RUNNER-VIA-ORCHESTRATOR" in raw
    assert "DESKTOP_GITHUB_RUNNER_RECOVERY_COMPLETED" in raw
    assert "host.github_runner.recover.v1" in raw

    # Bootstrap usa somente o Noteri e o action id fixo já allowlisted no Orchestrator.
    assert "runner-bootstrap:" in raw
    assert "if: ${{ inputs.mode == 'runner-bootstrap' }}" in raw
    assert "Bootstrap registered Desktop GitHub runner through control plane" in raw
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    runner_bootstrap = raw.split("  runner-bootstrap:", 1)[1].split(
        "  runner-canary:", 1
    )[0]
    assert "timeout-minutes: 12" in runner_bootstrap
    assert '"--timeout", "150"' in runner_bootstrap
    assert '"--timeout-seconds", "90"' in runner_bootstrap
    assert "desktop_runner_bootstrap_via_orchestrator.py" in raw
    assert "BOOTSTRAP-DESKTOP-GITHUB-RUNNER-VIA-ORCHESTRATOR" in raw
    assert "DESKTOP_GITHUB_RUNNER_LOCAL_BOOTSTRAP_VERIFIED" in raw
    assert "IDEMPOTENCY_NOT_PROVEN" in raw

    # Canário terminal exige pickup no runner físico exato, não apenas listener local.
    assert "runner-canary:" in raw
    assert "if: ${{ inputs.mode == 'runner-canary' }}" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "desktop_runner_pickup_canary.py" in raw
    assert "PROVE-DESKTOP-GITHUB-RUNNER-PICKUP" in raw
    assert "DESKTOP_GITHUB_RUNNER_PICKUP_PROVEN" in raw
    assert "DESKTOP-PDQK954" in raw

    # Todos os modos físicos não ligados à exceção de reboot usam a main canônica atual.
    assert raw.count("562fc4274aff24f7058cb135f27a509aa69031c1") == 4
    assert "881d9ca2f8e77025edb7298b22981109c567a730" not in raw
    assert "5af7b5ab6e31c24744176abd774855168c55953f" not in raw
