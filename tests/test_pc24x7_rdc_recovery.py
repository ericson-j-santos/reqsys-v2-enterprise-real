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
        m.task_end(r"\Automation\ArbitraryTask")
    with pytest.raises(m.RecoveryError, match="não allowlisted"):
        m.task_run(r"\Automation\ArbitraryTask")


def test_prefers_transport_proven_headless_and_arms_interactive_standby(monkeypatch):
    monkeypatch.setattr(m, "validate_host", lambda: m.EXPECTED_HOST)
    monkeypatch.setattr(
        m,
        "validate_headless_source",
        lambda: {"exists": True, "governed": True, "marker": m.HEADLESS_TRANSPORT_MARKER},
    )
    monkeypatch.setattr(
        m,
        "validate_interactive_source",
        lambda: {"exists": True, "governed": True, "marker": m.INTERACTIVE_MARKERS[-1]},
    )
    monkeypatch.setattr(m, "task_available", lambda task: True)
    monkeypatch.setattr(
        m,
        "wait_for_headless_ready",
        lambda: {"fresh": True, "ready": True, "age_seconds": 0.2, "reason": "fresh"},
    )
    observed = []
    monkeypatch.setattr(
        m,
        "restart_task",
        lambda task: observed.append(task) or {"end_returncode": 0, "run_returncode": 0},
    )

    result = m.recover(m.CONFIRM, "corr-test-headless")

    assert result["ok"] is True
    assert result["owner"] == "headless"
    assert result["mode"] == "headless_transport_proven_with_interactive_standby"
    assert result["fallback_armed"] is True
    assert result["headless_transport_guarded"] is True
    assert observed == [m.TASK_HEADLESS, m.TASK_INTERACTIVE]
    assert result["attempts"][0]["transport_claim"]["fresh"] is True


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
    monkeypatch.setattr(
        m,
        "restart_task",
        lambda task: observed.append(task) or {"end_returncode": 1, "run_returncode": 0},
    )

    result = m.recover(m.CONFIRM, "corr-test-interactive")

    assert result["ok"] is True
    assert result["owner"] == "interactive"
    assert result["mode"] == "interactive_fallback"
    assert result["fallback_armed"] is True
    assert observed == [m.TASK_INTERACTIVE]
    assert result["attempts"][0]["end_returncode"] == 1
    assert result["attempts"][0]["run_returncode"] == 0


def test_v3_headless_is_suppressed_instead_of_trusted(monkeypatch):
    monkeypatch.setattr(m, "validate_host", lambda: m.EXPECTED_HOST)
    monkeypatch.setattr(
        m,
        "validate_headless_source",
        lambda: {"exists": True, "governed": True, "marker": "// RDC_HEADLESS_V3_READY_CLAIM"},
    )
    monkeypatch.setattr(
        m,
        "validate_interactive_source",
        lambda: {"exists": True, "governed": True, "marker": m.INTERACTIVE_MARKERS[-1]},
    )
    monkeypatch.setattr(m, "task_available", lambda task: True)
    ended = []
    restarted = []
    monkeypatch.setattr(m, "task_end", lambda task: ended.append(task) or completed(0))
    monkeypatch.setattr(m, "clear_headless_claim", lambda: {"cleared": True})
    monkeypatch.setattr(
        m,
        "restart_task",
        lambda task: restarted.append(task) or {"end_returncode": 0, "run_returncode": 0},
    )

    result = m.recover(m.CONFIRM, "corr-test-v3-fallback")

    assert result["ok"] is True
    assert result["owner"] == "interactive"
    assert result["mode"] == "interactive_fallback"
    assert result["headless_transport_guarded"] is False
    assert ended == [m.TASK_HEADLESS]
    assert restarted == [m.TASK_INTERACTIVE]
    assert result["attempts"][0]["action"] == "suppress_unverified_transport_owner"


def test_read_headless_claim_requires_fresh_timezone_aware_ready_claim(monkeypatch, tmp_path):
    claim = tmp_path / "rdc-headless-owner.json"
    monkeypatch.setattr(m, "HEADLESS_CLAIM", claim)

    claim.write_text(
        '{"ready": true, "pid": 123, "updated_at": "2000-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    stale = m.read_headless_claim()
    assert stale["fresh"] is False
    assert stale["reason"] == "claim_stale"

    claim.write_text(
        '{"ready": true, "pid": 123, "updated_at": "not-a-date"}',
        encoding="utf-8",
    )
    invalid = m.read_headless_claim()
    assert invalid["fresh"] is False
    assert invalid["reason"] == "claim_invalid"


def test_restart_task_runs_even_when_end_reports_not_running(monkeypatch):
    observed = []
    monkeypatch.setattr(m, "task_end", lambda task: observed.append(("end", task)) or completed(1))
    monkeypatch.setattr(m, "task_run", lambda task: observed.append(("run", task)) or completed(0))

    result = m.restart_task(m.TASK_INTERACTIVE)

    assert observed == [("end", m.TASK_INTERACTIVE), ("run", m.TASK_INTERACTIVE)]
    assert result == {"end_returncode": 1, "run_returncode": 0}


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


def test_current_rdc_markers_are_allowlisted():
    assert "// RDC_HEADLESS_V3_READY_CLAIM" in m.HEADLESS_MARKERS
    assert m.HEADLESS_TRANSPORT_MARKER in m.HEADLESS_MARKERS
    assert "REM RDC_LAUNCHER_V5_READY_CLAIM" in m.INTERACTIVE_MARKERS