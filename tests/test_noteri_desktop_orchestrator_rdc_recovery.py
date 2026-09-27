from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "noteri_desktop_orchestrator_rdc_recovery.py"
SPEC = importlib.util.spec_from_file_location(
    "noteri_desktop_orchestrator_rdc_recovery", MODULE
)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def worker_status() -> dict:
    return {
        "workers": {
            "workers": [
                {
                    "worker_id": m.TARGET_WORKER,
                    "device_name": m.TARGET_HOST,
                    "controller_version": "0.2.53",
                    "fresh": True,
                    "eligible": True,
                    "controller_online": True,
                    "auth_valid": True,
                    "profile": "NORMAL",
                    "capabilities": {
                        "recovery_contract_version": 1,
                        "safe_task_types": [m.TASK_TYPE],
                    },
                }
            ]
        }
    }


def terminal_item(item_id: str) -> dict:
    return {
        "id": item_id,
        "status": "CONCLUÍDO",
        "result": {
            "handler": m.TASK_TYPE,
            "host": m.TARGET_HOST,
            "task": m.EXPECTED_TASK,
            "launcher": m.EXPECTED_LAUNCHER,
            "force_restart": True,
            "stopped_for_restart": True,
            "running_instance": "instance-guid",
            "before": {
                "enabled": True,
                "state": 4,
                "last_task_result": 0,
                "action_path": r"C:\Windows\System32\cmd.exe",
                "launcher": m.EXPECTED_LAUNCHER,
            },
            "after": {
                "enabled": True,
                "state": 4,
                "last_task_result": 0,
                "action_path": r"C:\Windows\System32\cmd.exe",
                "launcher": m.EXPECTED_LAUNCHER,
            },
        },
    }


def test_recovery_is_fixed_force_restart_and_idempotent(tmp_path: Path) -> None:
    item_id = "work-item-1"
    body_seen = []
    reads = {"item": 0}

    def requester(method, path, payload=None, *, timeout_seconds=5.0):
        if method == "GET" and path == "/readyz":
            return 200, {"ready": True}
        if method == "GET" and path == "/v1/status":
            return 200, worker_status()
        if method == "GET" and path.startswith("/v1/work-items/") and path != f"/v1/work-items/{item_id}":
            return 404, {"error": "work_item_not_found"}
        if method == "POST" and path == "/v1/intake":
            body_seen.append(payload)
            if len(body_seen) == 1:
                return 201, {
                    "replayed": False,
                    "item": {"id": item_id},
                    "dispatch": {"worker": {"device_name": m.TARGET_HOST}},
                }
            return 200, {
                "replayed": True,
                "item": {"id": item_id},
                "dispatch": None,
            }
        if method == "GET" and path == f"/v1/work-items/{item_id}":
            reads["item"] += 1
            return 200, {"item": terminal_item(item_id)}
        raise AssertionError((method, path, payload))

    evidence = m.recover(
        confirm=m.CONFIRM,
        correlation_id="rdc-recovery-test-123",
        evidence_file=tmp_path / "evidence.json",
        timeout_seconds=5,
        requester=requester,
        source_host="Noteri",
        platform="nt",
        sleep_fn=lambda _: None,
    )

    assert evidence["ok"] is True
    assert evidence["replay_idempotent"] is True
    assert evidence["independent_readback"] is True
    assert evidence["rdc_transport_online_proven"] is False
    assert body_seen[0]["payload"] == {
        "target_host": m.TARGET_HOST,
        "force_restart": True,
        "worker_hint": "builder",
    }
    assert body_seen[0]["risk"] == 2
    assert body_seen[0]["max_attempts"] == 1
    assert reads["item"] >= 2


def test_wrong_source_host_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(m.RecoveryError, match="source_host_not_authorized"):
        m.recover(
            confirm=m.CONFIRM,
            correlation_id="rdc-recovery-test-123",
            evidence_file=tmp_path / "evidence.json",
            requester=lambda *args, **kwargs: (200, {}),
            source_host="OTHER",
            platform="nt",
        )


def test_result_rejects_modified_task_or_launcher() -> None:
    item = terminal_item("work-item-1")
    item["result"]["task"] = r"\Automation\Other"
    with pytest.raises(m.RecoveryError, match="rdc_recovery_task_mismatch"):
        m.validate_result(item)

    item = terminal_item("work-item-1")
    item["result"]["launcher"] = r"C:\Other\start.cmd"
    with pytest.raises(m.RecoveryError, match="rdc_recovery_launcher_mismatch"):
        m.validate_result(item)


def test_control_plane_surface_blocks_arbitrary_post() -> None:
    with pytest.raises(m.RecoveryError, match="control_plane_post_not_allowlisted"):
        m.request_json("POST", "/readyz", {})
