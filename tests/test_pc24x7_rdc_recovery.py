from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "pc24x7_rdc_recovery.py"
SPEC = importlib.util.spec_from_file_location("pc24x7_rdc_recovery", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def completed(rc: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["schtasks"], rc, stdout="", stderr="")


def test_rejects_other_host(monkeypatch):
    monkeypatch.setattr(m.os, "name", "nt")
    monkeypatch.setattr(m.socket, "gethostname", lambda: "Noteri")
    with pytest.raises(m.RecoveryError, match="host não autorizado"):
        m.validate_host()


def test_task_name_is_strictly_allowlisted():
    with pytest.raises(m.RecoveryError, match="não allowlisted"):
        m.task_query(r"\Automation\ArbitraryTask")
    with pytest.raises(m.RecoveryError, match="não allowlisted"):
        m.task_run(r"\Automation\ArbitraryTask")


def test_prefers_governed_headless_task(monkeypatch):
    monkeypatch.setattr(m, "validate_host", lambda: m.EXPECTED_HOST)
    monkeypatch.setattr(m, "validate_headless_source", lambda: {"exists": True, "governed": True})
    monkeypatch.setattr(
        m,
        "validate_interactive_source",
        lambda: {"exists": True, "governed": True, "marker": m.INTERACTIVE_MARKERS[1]},
    )
    monkeypatch.setattr(m, "task_available", lambda task: True)
    observed = []
    monkeypatch.setattr(m, "task_run", lambda task: observed.append(task) or completed(0))

    result = m.recover(m.CONFIRM, "corr-test-headless")

    assert result["ok"] is True
    assert result["owner"] == "headless"
    assert observed == [m.TASK_HEADLESS]


def test_falls_back_to_governed_interactive_task(monkeypatch):
    monkeypatch.setattr(m, "validate_host", lambda: m.EXPECTED_HOST)
    monkeypatch.setattr(m, "validate_headless_source", lambda: {"exists": False, "governed": False})
    monkeypatch.setattr(
        m,
        "validate_interactive_source",
        lambda: {"exists": True, "governed": True, "marker": m.INTERACTIVE_MARKERS[0]},
    )
    monkeypatch.setattr(m, "task_available", lambda task: task == m.TASK_INTERACTIVE)
    observed = []
    monkeypatch.setattr(m, "task_run", lambda task: observed.append(task) or completed(0))

    result = m.recover(m.CONFIRM, "corr-test-interactive")

    assert result["ok"] is True
    assert result["owner"] == "interactive"
    assert observed == [m.TASK_INTERACTIVE]


def test_fails_closed_when_sources_are_not_governed(monkeypatch):
    monkeypatch.setattr(m, "validate_host", lambda: m.EXPECTED_HOST)
    monkeypatch.setattr(m, "validate_headless_source", lambda: {"exists": True, "governed": False})
    monkeypatch.setattr(
        m,
        "validate_interactive_source",
        lambda: {"exists": True, "governed": False, "marker": None},
    )
    monkeypatch.setattr(m, "task_available", lambda task: True)
    with pytest.raises(m.RecoveryError, match="nenhuma tarefa RDC governada"):
        m.recover(m.CONFIRM, "corr-negative")


def test_confirmation_is_required():
    with pytest.raises(m.RecoveryError, match="confirmação inválida"):
        m.recover("NO", "corr-negative")


def test_workflow_contract_is_fixed_to_pc24x7_desktop():
    workflow = (ROOT / ".github/workflows/desktop-rdc-recovery.yml").read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in workflow
    assert "--confirm RECOVER-GOVERNED-RDC" in workflow
    assert "workflow_dispatch:" in workflow
    assert "workflow_call:" not in workflow
    assert "inputs:" not in workflow
    assert "production_touched" not in workflow.lower()
