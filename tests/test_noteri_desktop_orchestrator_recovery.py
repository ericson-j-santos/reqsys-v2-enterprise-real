from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "noteri_desktop_orchestrator_recovery.py"
SPEC = importlib.util.spec_from_file_location("noteri_desktop_orchestrator_recovery", SCRIPT)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_prefers_runner_recovery_when_available():
    task, payload = m.choose_task({
        "runner_recovery_capable": True,
        "rdc_recovery_capable": True,
    })
    assert task == m.RUNNER_RECOVERY_TASK
    assert payload == {"target_host": m.TARGET_HOST}


def test_falls_back_to_rdc_recovery_without_arbitrary_command():
    task, payload = m.choose_task({
        "runner_recovery_capable": False,
        "rdc_recovery_capable": True,
    })
    assert task == m.RDC_RECOVERY_TASK
    assert payload == {"target_host": m.TARGET_HOST, "force_restart": True}


def test_rejects_when_no_allowlisted_recovery_exists():
    with pytest.raises(m.RecoveryError, match="no_supported"):
        m.choose_task({
            "runner_recovery_capable": False,
            "rdc_recovery_capable": False,
        })


def test_recovery_posts_idempotent_allowlisted_task_and_reads_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "require_noteri", lambda: None)
    monkeypatch.setattr(m, "desktop_worker_snapshot", lambda: {
        "fresh": True,
        "controller_online": True,
        "auth_valid": True,
        "eligible": True,
        "profile": "NORMAL",
        "runner_recovery_capable": False,
        "rdc_recovery_capable": True,
    })
    calls = []
    def fake_request(method, path, payload=None):
        calls.append((method, path, payload))
        if path == "/v1/intake":
            assert payload["task_type"] == m.RDC_RECOVERY_TASK
            assert payload["payload"] == {"target_host": m.TARGET_HOST, "force_restart": True}
            assert payload["idempotency_key"] == "desktop-control-recovery:run-123"
            return 201, {"created": True, "replayed": False, "item": {"id": "item-1"}}
        if path == "/v1/work-items/item-1":
            return 200, {"item": {
                "id": "item-1",
                "status": "CONCLUÍDO",
                "result": {
                    "handler": m.RDC_RECOVERY_TASK,
                    "host": m.TARGET_HOST,
                    "force_restart": True,
                },
            }}
        raise AssertionError(path)
    monkeypatch.setattr(m, "request_json", fake_request)
    result = m.recover(
        confirm=m.CONFIRM,
        operation_id="run-123",
        correlation_id="corr-run-123",
        evidence_file=tmp_path / "evidence.json",
        sleep_fn=lambda _: None,
    )
    assert result["ok"] is True
    assert result["handler_confirmed"] is True
    assert result["arbitrary_command_enabled"] is False
    assert all("shell" not in str(call).lower() for call in calls)
