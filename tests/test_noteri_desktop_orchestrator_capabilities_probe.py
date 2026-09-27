from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "noteri_desktop_orchestrator_capabilities_probe.py"
SPEC = importlib.util.spec_from_file_location(
    "noteri_desktop_orchestrator_capabilities_probe", MODULE
)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def status_payload(*, safe_tasks: list[str], source_sha: str = "a" * 40) -> dict:
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
                        "runtime_source_sha": source_sha,
                        "worker_instance_id": "b" * 32,
                        "safe_task_types": safe_tasks,
                    },
                }
            ]
        }
    }


def test_probe_observes_capabilities_without_mutation() -> None:
    calls = []

    def requester(path: str, *, timeout_seconds: float = 5.0):
        calls.append((path, timeout_seconds))
        if path == "/readyz":
            return 200, {"ready": True}
        if path == "/v1/status":
            return 200, status_payload(
                safe_tasks=[
                    "host.inventory.files.v1",
                    "host.orchestrator.refresh.v1",
                    "host.github_runner.recover.v1",
                ]
            )
        raise AssertionError(path)

    result = m.probe(
        confirm=m.CONFIRM,
        correlation_id="capability-probe-1234",
        timeout_seconds=5,
        requester=requester,
        source_host="Noteri",
        platform="nt",
    )

    assert calls == [("/readyz", 5), ("/v1/status", 5)]
    assert result["ok"] is True
    assert result["read_only"] is True
    assert result["http_methods_used"] == ["GET"]
    assert result["worker"]["runtime_source_sha"] == "a" * 40
    assert result["worker"]["interesting_capabilities"]["host.inventory.files.v1"] is True
    assert result["worker"]["interesting_capabilities"]["host.github_runner.bootstrap.v1"] is False


def test_wrong_source_host_fails_closed() -> None:
    with pytest.raises(m.ProbeError, match="source_host_not_authorized"):
        m.probe(
            confirm=m.CONFIRM,
            correlation_id="capability-probe-1234",
            timeout_seconds=5,
            requester=lambda *args, **kwargs: (200, {}),
            source_host="OTHER",
            platform="nt",
        )


def test_request_surface_is_get_only_and_allowlisted() -> None:
    with pytest.raises(m.ProbeError, match="control_plane_path_not_allowlisted"):
        m.request_json("/v1/intake")


def test_invalid_runtime_identity_fails_closed() -> None:
    payload = status_payload(
        safe_tasks=["host.inventory.files.v1"],
        source_sha="main",
    )
    with pytest.raises(m.ProbeError, match="desktop_runtime_source_sha_invalid"):
        m.extract_worker(payload)
