from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "scripts" / "noteri_control_plane_probe.py"
WATCHDOG_PATH = ROOT / "scripts" / "noteri_control_plane_watchdog.py"
WORKFLOW = ROOT / ".github/workflows/noteri-control-plane-probe.yml"
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
