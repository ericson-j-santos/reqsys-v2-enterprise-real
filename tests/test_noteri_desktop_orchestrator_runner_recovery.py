from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "noteri_desktop_orchestrator_runner_recovery.py"
SPEC = importlib.util.spec_from_file_location("noteri_desktop_orchestrator_runner_recovery", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_contract_is_fixed_and_has_no_remote_shell_surface() -> None:
    raw = MODULE.read_text(encoding="utf-8").casefold()
    assert m.BASE_URL == "http://DESKTOP-PDQK954:8787"
    assert m.WORKER_ID == "desktop-pdqk954"
    assert m.TASK_TYPE == "host.github_runner.recover.v1"
    assert m.TARGET_HOST == "DESKTOP-PDQK954"
    assert "subprocess" not in raw
    assert "powershell" not in raw
    assert "cmd.exe" not in raw
    assert "shell=true" not in raw


def test_recovery_requires_advertised_capability(monkeypatch) -> None:
    monkeypatch.setattr(
        m,
        "_desktop_worker",
        lambda: {
            "worker_id": m.WORKER_ID,
            "capabilities": {"safe_task_types": ["orchestrator.selftest"]},
        },
    )
    try:
        m.recover("corr-test-capability-001", 10)
    except m.RecoveryError as exc:
        assert "desktop_worker_capability_missing" in str(exc)
    else:
        raise AssertionError("capability gate must fail closed")


def test_safe_task_types_is_fail_closed() -> None:
    assert m._safe_task_types({}) == []
    assert m._safe_task_types({"capabilities": {}}) == []
    assert m._safe_task_types({"capabilities": {"safe_task_types": "invalid"}}) == []
