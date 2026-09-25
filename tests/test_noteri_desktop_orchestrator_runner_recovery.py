from __future__ import annotations

import importlib.util
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "noteri_desktop_orchestrator_runner_recovery.py"
SPEC = importlib.util.spec_from_file_location("noteri_desktop_orchestrator_runner_recovery", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def _worker(*task_types: str) -> dict:
    return {
        "worker_id": m.WORKER_ID,
        "fresh": True,
        "controller_online": True,
        "auth_valid": True,
        "capabilities": {"safe_task_types": list(task_types)},
    }


def test_contract_is_fixed_and_has_no_remote_shell_surface() -> None:
    raw = MODULE.read_text(encoding="utf-8").casefold()
    assert m.BASE_URL == "http://DESKTOP-PDQK954:8787"
    assert m.WORKER_ID == "desktop-pdqk954"
    assert m.TASK_TYPE == "host.github_runner.recover.v1"
    assert m.REFRESH_TASK_TYPE == "host.orchestrator.refresh.v1"
    assert m.ORCHESTRATOR_SHA == "63d26ff024e9f782bdddb7e954a6e247c8ef13b7"
    assert m.TARGET_HOST == "DESKTOP-PDQK954"
    assert "subprocess" not in raw
    assert "powershell" not in raw
    assert "cmd.exe" not in raw
    assert "shell=true" not in raw


def test_unrecoverable_runtime_drift_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(m, "_desktop_worker", lambda: _worker("orchestrator.selftest"))
    try:
        m.recover("corr-test-capability-001", 10)
    except m.RecoveryError as exc:
        assert (
            str(exc)
            == "desktop_worker_runtime_drift_unrecoverable:"
            "runner_and_refresh_capabilities_missing"
        )
    else:
        raise AssertionError("runtime drift without refresh handler must fail closed")


def test_recovery_refreshes_runtime_then_recovers_runner(monkeypatch) -> None:
    before = _worker(m.REFRESH_TASK_TYPE)
    refreshed = _worker(m.REFRESH_TASK_TYPE, m.TASK_TYPE)
    reads = iter([before, refreshed])
    monkeypatch.setattr(m, "_desktop_worker", lambda: next(reads))
    monkeypatch.setattr(m, "_wait_for_runner_capability", lambda deadline: refreshed)

    calls: list[dict] = []

    def fake_submit_task(**kwargs):
        calls.append(kwargs)
        task_type = kwargs["task_type"]
        if task_type == m.REFRESH_TASK_TYPE:
            result = {
                "handler": m.REFRESH_TASK_TYPE,
                "expected_sha": m.ORCHESTRATOR_SHA,
            }
        else:
            result = {
                "handler": m.TASK_TYPE,
                "result": "recovered",
            }
        return {
            "event_id": f"evt-{len(calls)}",
            "idempotency_key": f"idem-{len(calls)}",
            "work_item_id": f"item-{len(calls)}",
            "replayed": False,
            "result": result,
        }

    monkeypatch.setattr(m, "_submit_task", fake_submit_task)

    result = m.recover("corr-refresh-001", 30)

    assert [call["task_type"] for call in calls] == [
        m.REFRESH_TASK_TYPE,
        m.TASK_TYPE,
    ]
    assert calls[0]["payload"] == {
        "target_host": m.TARGET_HOST,
        "expected_sha": m.ORCHESTRATOR_SHA,
    }
    assert calls[1]["payload"] == {"target_host": m.TARGET_HOST}
    assert result["ok"] is True
    assert result["runtime_refresh"]["attempted"] is True
    assert result["worker_after"]["runner_recovery_capability"] is True


def test_submit_task_uses_canonical_status_contract(monkeypatch) -> None:
    responses = iter(
        [
            (
                201,
                {
                    "item": {"id": "item-1", "status": "PENDENTE"},
                    "replayed": False,
                    "dispatch": {"worker": {"worker_id": m.WORKER_ID}},
                },
            ),
            (
                200,
                {
                    "item": {
                        "id": "item-1",
                        "status": "CONCLUÍDO",
                        "result": {"handler": m.TASK_TYPE},
                    }
                },
            ),
        ]
    )
    monkeypatch.setattr(m, "_request", lambda *args, **kwargs: next(responses))

    result = m._submit_task(
        task_type=m.TASK_TYPE,
        payload={"target_host": m.TARGET_HOST},
        correlation_id="corr-status-001",
        idempotency_suffix="runner-recovery",
        deadline=time.monotonic() + 2,
    )

    assert result["work_item_id"] == "item-1"
    assert result["result"]["handler"] == m.TASK_TYPE


def test_safe_task_types_is_fail_closed() -> None:
    assert m._safe_task_types({}) == []
    assert m._safe_task_types({"capabilities": {}}) == []
    assert m._safe_task_types({"capabilities": {"safe_task_types": "invalid"}}) == []
