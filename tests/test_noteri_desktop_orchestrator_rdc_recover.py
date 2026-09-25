from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "noteri_desktop_orchestrator_rdc_recover.py"
spec = importlib.util.spec_from_file_location("rdc_recovery", SCRIPT)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_recovery_uses_fixed_task_and_target():
    item_id = "item-rdc-001"
    calls = []
    state = {"reads": 0}

    def transport(method, path, payload):
        calls.append((method, path, payload))
        if method == "GET" and path == "/readyz":
            return 200, {"ready": True}
        if method == "GET" and path == "/v1/workers":
            return 200, {
                "workers": [{
                    "worker_id": "desktop-pdqk954",
                    "device_name": "DESKTOP-PDQK954",
                    "controller_version": "0.2.51",
                    "fresh": True,
                    "eligible": True,
                    "capabilities": {"safe_task_types": ["host.rdc.recover.v1"]},
                }]
            }
        if method == "POST" and path == "/v1/intake":
            assert payload["task_type"] == "host.rdc.recover.v1"
            assert payload["payload"] == {
                "target_host": "DESKTOP-PDQK954",
                "force_restart": True,
            }
            assert payload["risk"] == 1
            return 201, {
                "created": True,
                "replayed": False,
                "item": {"id": item_id, "status": "EM ANDAMENTO"},
            }
        if method == "GET" and path == f"/v1/work-items/{item_id}":
            state["reads"] += 1
            return 200, {
                "item": {
                    "id": item_id,
                    "status": "CONCLUÍDO",
                    "result": {
                        "handler": "host.rdc.recover.v1",
                        "host": "DESKTOP-PDQK954",
                        "worker_id": "desktop-pdqk954",
                        "device_name": "DESKTOP-PDQK954",
                        "force_restart": True,
                        "stopped_for_restart": True,
                    },
                }
            }
        raise AssertionError((method, path, payload))

    result = m.recover(
        "corr-rdc-recovery-001",
        transport=transport,
        timeout_seconds=5,
        sleep_fn=lambda _: None,
    )
    assert result["ok"] is True
    assert result["target_host"] == "DESKTOP-PDQK954"
    assert result["task_type"] == "host.rdc.recover.v1"
    assert state["reads"] == 1


def test_recovery_fails_closed_when_capability_missing():
    def transport(method, path, payload):
        if path == "/readyz":
            return 200, {"ready": True}
        if path == "/v1/workers":
            return 200, {
                "workers": [{
                    "worker_id": "desktop-pdqk954",
                    "device_name": "DESKTOP-PDQK954",
                    "controller_version": "0.2.51",
                    "fresh": True,
                    "eligible": True,
                    "capabilities": {"safe_task_types": ["orchestrator.selftest"]},
                }]
            }
        raise AssertionError("intake must not be called")

    try:
        m.recover(
            "corr-rdc-recovery-002",
            transport=transport,
            timeout_seconds=5,
            sleep_fn=lambda _: None,
        )
    except m.RecoveryError as exc:
        assert "not_eligible" in str(exc)
    else:
        raise AssertionError("expected fail closed")
