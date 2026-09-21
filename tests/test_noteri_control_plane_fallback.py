from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "scripts" / "noteri_control_plane_probe.py"
WATCHDOG_PATH = ROOT / "scripts" / "noteri_control_plane_watchdog.py"
WORKFLOW = ROOT / ".github/workflows/noteri-control-plane-probe.yml"
HEADLESS_WORKFLOW = ROOT / ".github/workflows/noteri-headless-control-plane-activation.yml"
HEADLESS_LAUNCHER = ROOT / "scripts" / "noteri_control_plane_watchdog_uac_launcher.py"
POLICY = ROOT / ".github/self-hosted-runner-policy.json"

PROBE_SPEC = importlib.util.spec_from_file_location("noteri_control_plane_probe", PROBE_PATH)
assert PROBE_SPEC and PROBE_SPEC.loader
probe = importlib.util.module_from_spec(PROBE_SPEC)
PROBE_SPEC.loader.exec_module(probe)

WATCHDOG_SPEC = importlib.util.spec_from_file_location("noteri_control_plane_watchdog", WATCHDOG_PATH)
assert WATCHDOG_SPEC and WATCHDOG_SPEC.loader
watchdog = importlib.util.module_from_spec(WATCHDOG_SPEC)
WATCHDOG_SPEC.loader.exec_module(watchdog)


def test_probe_rejects_other_host(monkeypatch) -> None:
    monkeypatch.setattr(probe.os, "name", "nt")
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    with pytest.raises(probe.ProbeError, match="host não autorizado"):
        probe.validate_host()


def test_probe_requires_exact_confirmation() -> None:
    with pytest.raises(probe.ProbeError, match="confirmação inválida"):
        probe.probe("NO", "corr-12345678")


def test_probe_proves_runner_without_rdc(monkeypatch) -> None:
    monkeypatch.setattr(probe, "validate_host", lambda: "Noteri")
    monkeypatch.setattr(probe, "runner_listener_detected", lambda: True)
    monkeypatch.setenv("RUNNER_NAME", "noteri-reqsys-dev")
    monkeypatch.setenv("RUNNER_OS", "Windows")
    monkeypatch.setenv("RUNNER_ARCH", "X64")
    result = probe.probe(probe.CONFIRM, "corr-noteri-probe")
    assert result["ok"] is True
    assert result["host"] == "Noteri"
    assert result["runner_listener_detected"] is True
    assert result["rdc_required"] is False
    assert result["production_touched"] is False
    assert result["secrets_read"] is False


def test_watchdog_runner_contract_never_reads_runner_contents(tmp_path: Path) -> None:
    root = tmp_path / "actions-runner"
    (root / "bin").mkdir(parents=True)
    (root / ".runner").write_text("sensitive-placeholder", encoding="utf-8")
    (root / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (root / "bin" / "Runner.Listener.exe").write_bytes(b"stub")
    assert watchdog.validate_runner_home(root) == root.resolve()


def test_watchdog_cycle_starts_runner_when_listener_missing(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "actions-runner"
    (root / "bin").mkdir(parents=True)
    (root / ".runner").write_text("opaque", encoding="utf-8")
    (root / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (root / "bin" / "Runner.Listener.exe").write_bytes(b"stub")
    observed = iter([False, True])
    monkeypatch.setattr(watchdog, "require_noteri", lambda: "Noteri")
    monkeypatch.setattr(watchdog, "runner_running", lambda: next(observed))
    monkeypatch.setattr(watchdog, "start_runner", lambda path: True)
    monkeypatch.setattr(watchdog, "runtime_root", lambda: tmp_path / "runtime")
    monkeypatch.setattr(watchdog, "atomic_json", lambda path, payload: None)
    result = watchdog.cycle(root)
    assert result["ok"] is True
    assert result["runner_start_attempted"] is True
    assert result["runner_started"] is True
    assert result["rdc_required"] is False


def test_workflow_and_policy_are_fixed_to_noteri() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in workflow
    assert "--confirm PROBE-NOTERI-CONTROL-PLANE" in workflow
    assert "workflow_dispatch:" in workflow
    assert "inputs:" not in workflow
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert ".github/workflows/noteri-control-plane-probe.yml" in policy["approved_workflows"]


def test_watchdog_installs_hkcu_fallback_when_startup_task_denied(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "actions-runner"
    (root / "bin").mkdir(parents=True)
    (root / ".runner").write_text("opaque", encoding="utf-8")
    (root / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (root / "bin" / "Runner.Listener.exe").write_bytes(b"stub")

    repo_root = tmp_path / "repo"
    scripts = repo_root / "scripts"
    scripts.mkdir(parents=True)
    source = scripts / "noteri_control_plane_watchdog.py"
    source.write_text(WATCHDOG_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(watchdog, "require_noteri", lambda: "Noteri")
    monkeypatch.setattr(watchdog, "runtime_root", lambda: tmp_path / "runtime")
    monkeypatch.setattr(
        watchdog,
        "register_task",
        lambda **kwargs: (_ for _ in ()).throw(PermissionError("Access is denied")),
    )
    monkeypatch.setattr(
        watchdog,
        "install_logon_fallback",
        lambda **kwargs: {
            "exists": True,
            "trigger": "AtLogon",
            "scope": "HKCU",
            "headless": False,
        },
    )
    monkeypatch.setattr(
        watchdog,
        "cycle",
        lambda runner_home: {"ok": True, "runner_running_after": True},
    )

    result = watchdog.install(
        repo_root,
        root,
        "a" * 40,
        watchdog.INSTALL_CONFIRM,
    )
    assert result["runtime_ok"] is True
    assert result["activation_pending"] is True
    assert result["runtime_persistent_after_login"] is True
    assert result["headless_persistence"] is False
    assert result["logon_fallback"]["scope"] == "HKCU"


def test_headless_activation_workflow_is_fixed_to_noteri_and_uac() -> None:
    workflow = HEADLESS_WORKFLOW.read_text(encoding="utf-8")
    launcher = HEADLESS_LAUNCHER.read_text(encoding="utf-8")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in workflow
    assert "shell: powershell" in workflow
    assert "shell: pwsh" not in workflow
    assert "--confirm LAUNCH-NOTERI-CONTROL-PLANE-WATCHDOG-UAC" in workflow
    assert "workflow_dispatch:" in workflow
    assert "inputs:" not in workflow
    assert "ShellExecuteW" in launcher
    assert "--result-path" in launcher
    assert "ELEVATED_INSTALL_FAILED" in launcher
    assert "schtasks.exe" in launcher
    assert "schtasks_xml" in launcher
    assert '"runas"' in launcher
    assert 'EXPECTED_HOST' not in launcher or "watchdog.EXPECTED_HOST" in launcher
    assert "AtStartup" in launcher or "trigger_at_startup" in launcher
    assert "S4U" in launcher
    assert "reboot_performed" in launcher
    assert ".github/workflows/noteri-headless-control-plane-activation.yml" in policy["approved_workflows"]


def test_watchdog_creates_automation_folder_when_missing() -> None:
    class Root:
        def __init__(self) -> None:
            self.created = None

        def CreateFolder(self, name: str):
            self.created = name
            return {"folder": name}

    class Service:
        def __init__(self) -> None:
            self.root = Root()

        def GetFolder(self, path: str):
            if path == "\\":
                return self.root
            raise RuntimeError("missing")

    service = Service()
    folder = watchdog.ensure_task_folder(service)
    assert folder == {"folder": "Automation"}
    assert service.root.created == "Automation"
