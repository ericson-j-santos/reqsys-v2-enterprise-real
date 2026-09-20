from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "desktop_control_plane_maintenance_client.py"
SPEC = importlib.util.spec_from_file_location("desktop_control_plane_maintenance_client", SCRIPT)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def worker_snapshot(*, safe_task_types=None, fresh=True, eligible=True):
    return {
        "workers": {
            "workers": [
                {
                    "worker_id": "desktop-pdqk954",
                    "device_name": "DESKTOP-PDQK954",
                    "fresh": fresh,
                    "eligible": eligible,
                    "profile": "NORMAL",
                    "controller_version": "0.2.51",
                    "last_heartbeat": "2026-09-20T22:00:00+00:00",
                    "capabilities": {
                        "safe_task_types": safe_task_types
                        or ["host.rdc.recover.v1", "orchestrator.selftest"]
                    },
                }
            ]
        },
        "by_status": {"PENDENTE": 0},
    }


def test_endpoint_is_fixed_to_governed_desktop():
    assert m.validate_endpoint("http://DESKTOP-PDQK954:18787") == m.DEFAULT_ENDPOINT
    assert m.validate_endpoint("http://desktop-pdqk954:18787/") == m.DEFAULT_ENDPOINT

    for invalid in (
        "https://DESKTOP-PDQK954:18787",
        "http://Noteri:18787",
        "http://DESKTOP-PDQK954:9999",
        "http://user@DESKTOP-PDQK954:18787",
        "http://DESKTOP-PDQK954:18787/v1/status",
        "http://DESKTOP-PDQK954:18787?x=1",
    ):
        with pytest.raises(m.MaintenanceClientError):
            m.validate_endpoint(invalid)


def test_action_allowlist_excludes_reboot_and_arbitrary_commands():
    assert set(m.ACTION_CONTRACTS) == {"rdc", "github-runner", "refresh"}
    assert all(
        contract["task_type"] != "host.reboot.once.v1"
        for contract in m.ACTION_CONTRACTS.values()
    )
    with pytest.raises(m.MaintenanceClientError, match="não allowlisted"):
        m.build_action("shell")
    rdc = m.build_action("rdc")
    assert rdc[0] == "host.rdc.recover.v1"
    assert rdc[1] == 2
    assert rdc[2] == {
        "target_host": "DESKTOP-PDQK954",
        "force_restart": True,
    }


def test_refresh_requires_exact_sha():
    sha = "a" * 40
    task_type, risk, payload = m.build_action("refresh", expected_sha=sha)
    assert task_type == "host.orchestrator.refresh.v1"
    assert risk == 2
    assert payload == {"target_host": "DESKTOP-PDQK954", "expected_sha": sha}

    with pytest.raises(m.MaintenanceClientError, match="expected_sha"):
        m.build_action("refresh")
    with pytest.raises(m.MaintenanceClientError, match="expected_sha"):
        m.build_action("refresh", expected_sha="ABC")


def test_capability_gate_is_fail_closed():
    snapshot = worker_snapshot()
    worker = m.require_worker_capability(snapshot, task_type="host.rdc.recover.v1")
    assert worker["worker_id"] == "desktop-pdqk954"

    with pytest.raises(m.MaintenanceClientError, match="heartbeat"):
        m.require_worker_capability(
            worker_snapshot(fresh=False), task_type="host.rdc.recover.v1"
        )
    with pytest.raises(m.MaintenanceClientError, match="não elegível"):
        m.require_worker_capability(
            worker_snapshot(eligible=False), task_type="host.rdc.recover.v1"
        )
    with pytest.raises(m.MaintenanceClientError, match="capability"):
        m.require_worker_capability(
            worker_snapshot(safe_task_types=["orchestrator.selftest"]),
            task_type="host.rdc.recover.v1",
        )


def test_submit_rdc_dispatches_to_exact_worker_and_reads_terminal(monkeypatch):
    calls = []
    snapshot = worker_snapshot()

    def fake_request(method, url, payload=None, *, timeout=5.0):
        calls.append((method, url, payload))
        if method == "GET" and url.endswith("/v1/status"):
            return 200, snapshot
        if method == "POST" and url.endswith("/v1/intake"):
            assert payload["task_type"] == "host.rdc.recover.v1"
            assert payload["payload"] == {
                "target_host": "DESKTOP-PDQK954",
                "force_restart": True,
            }
            assert payload["risk"] == 2
            return 201, {
                "item": {"id": "item-rdc-1", "status": "EM ANDAMENTO"},
                "created": True,
                "replayed": False,
                "dispatch": {
                    "dispatch_id": "dispatch-1",
                    "worker": {
                        "worker_id": "desktop-pdqk954",
                        "device_name": "DESKTOP-PDQK954",
                    },
                },
            }
        if method == "GET" and url.endswith("/v1/work-items/item-rdc-1"):
            return 200, {
                "item": {
                    "id": "item-rdc-1",
                    "status": "CONCLUÍDO",
                    "result": {
                        "handler": "host.rdc.recover.v1",
                        "host": "DESKTOP-PDQK954",
                        "controller_semantic_ok": True,
                    },
                }
            }
        raise AssertionError((method, url, payload))

    monkeypatch.setattr(m, "request_json", fake_request)
    result = m.submit_action(
        m.DEFAULT_ENDPOINT,
        action="rdc",
        correlation_id="corr-test-rdc",
        timeout_seconds=2,
    )
    assert result["ok"] is True
    assert result["item_status"] == "CONCLUÍDO"
    assert result["worker_id"] == "desktop-pdqk954"
    assert result["replayed"] is False
    assert result["production_touched"] is False
    assert result["secrets_read"] is False
    assert result["reboot_performed"] is False
    assert len(calls) == 3


def test_replay_uses_same_item_without_second_dispatch(monkeypatch):
    snapshot = worker_snapshot()

    def fake_request(method, url, payload=None, *, timeout=5.0):
        if method == "GET" and url.endswith("/v1/status"):
            return 200, snapshot
        if method == "POST" and url.endswith("/v1/intake"):
            return 200, {
                "item": {"id": "item-rdc-existing", "status": "CONCLUÍDO"},
                "created": False,
                "replayed": True,
                "dispatch": None,
            }
        if method == "GET" and url.endswith("/v1/work-items/item-rdc-existing"):
            return 200, {
                "item": {
                    "id": "item-rdc-existing",
                    "status": "CONCLUÍDO",
                    "result": {
                        "handler": "host.rdc.recover.v1",
                        "controller_semantic_ok": True,
                    },
                }
            }
        raise AssertionError((method, url, payload))

    monkeypatch.setattr(m, "request_json", fake_request)
    first = m.deterministic_identity("rdc", "corr-replay")
    second = m.deterministic_identity("rdc", "corr-replay")
    assert first == second

    result = m.submit_action(
        m.DEFAULT_ENDPOINT,
        action="rdc",
        correlation_id="corr-replay",
        timeout_seconds=2,
    )
    assert result["ok"] is True
    assert result["replayed"] is True
    assert result["item_id"] == "item-rdc-existing"


def test_terminal_failure_remains_failure(monkeypatch):
    snapshot = worker_snapshot()

    def fake_request(method, url, payload=None, *, timeout=5.0):
        if method == "GET" and url.endswith("/v1/status"):
            return 200, snapshot
        if method == "POST":
            return 201, {
                "item": {"id": "item-fail", "status": "EM ANDAMENTO"},
                "replayed": False,
                "dispatch": {
                    "worker": {
                        "worker_id": "desktop-pdqk954",
                        "device_name": "DESKTOP-PDQK954",
                    }
                },
            }
        return 200, {
            "item": {
                "id": "item-fail",
                "status": "BLOQUEADO",
                "last_error": "MaintenanceError: controlled failure",
            }
        }

    monkeypatch.setattr(m, "request_json", fake_request)
    result = m.submit_action(
        m.DEFAULT_ENDPOINT,
        action="rdc",
        correlation_id="corr-fail",
        timeout_seconds=2,
    )
    assert result["ok"] is False
    assert result["item_status"] == "BLOQUEADO"
    assert "controlled failure" in result["last_error"]


def test_rdc_completed_without_semantic_witness_fails_closed(monkeypatch):
    snapshot = worker_snapshot()

    def fake_request(method, url, payload=None, *, timeout=5.0):
        if method == "GET" and url.endswith("/v1/status"):
            return 200, snapshot
        if method == "POST":
            return 201, {
                "item": {"id": "item-false-green", "status": "EM ANDAMENTO"},
                "replayed": False,
                "dispatch": {
                    "worker": {
                        "worker_id": "desktop-pdqk954",
                        "device_name": "DESKTOP-PDQK954",
                    }
                },
            }
        return 200, {
            "item": {
                "id": "item-false-green",
                "status": "CONCLUÍDO",
                "result": {
                    "handler": "host.rdc.recover.v1",
                    "host": "DESKTOP-PDQK954",
                    "after": {"state": 4},
                },
            }
        }

    monkeypatch.setattr(m, "request_json", fake_request)
    result = m.submit_action(
        m.DEFAULT_ENDPOINT,
        action="rdc",
        correlation_id="corr-false-green",
        timeout_seconds=2,
    )
    assert result["queue_completed"] is True
    assert result["semantic_ok"] is False
    assert result["ok"] is False
    assert result["last_error"] == "controller_semantic_evidence_missing"
