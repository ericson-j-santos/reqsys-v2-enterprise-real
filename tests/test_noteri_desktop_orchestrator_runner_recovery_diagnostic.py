from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "noteri_desktop_orchestrator_runner_recovery_diagnostic.py"
SPEC = importlib.util.spec_from_file_location(
    "noteri_desktop_orchestrator_runner_recovery_diagnostic", MODULE
)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_status_blocker_is_read_without_replay(tmp_path: Path) -> None:
    calls = []

    def requester(method, path, payload=None, *, timeout_seconds=5.0):
        calls.append((method, path))
        if path == "/readyz":
            return 200, {"ready": True}
        if path == "/v1/status":
            return 200, {
                "blockers": [
                    {
                        "id": "item-1",
                        "correlation_id": m.HISTORICAL_CORRELATION_ID,
                        "target_worker": "builder",
                        "last_error": "MaintenanceError:runner_service_not_found",
                        "attempts": 1,
                    }
                ]
            }
        raise AssertionError((method, path))

    result = m.diagnose(
        confirm=m.CONFIRM,
        evidence_file=tmp_path / "evidence.json",
        requester=requester,
        source_host="Noteri",
        platform="nt",
    )

    assert result["ok"] is True
    assert result["lookup_source"] == "status_blockers"
    assert result["idempotent_replay_used"] is False
    assert result["physical_recovery_repeated"] is False
    assert calls == [("GET", "/readyz"), ("GET", "/v1/status")]


def test_missing_blocker_uses_only_idempotent_replay_and_get(tmp_path: Path) -> None:
    body = m.build_historical_request()
    item_id = "item-2"
    seen_post = []

    def requester(method, path, payload=None, *, timeout_seconds=5.0):
        if method == "GET" and path == "/readyz":
            return 200, {"ready": True}
        if method == "GET" and path == "/v1/status":
            return 200, {"blockers": []}
        if method == "POST" and path == "/v1/intake":
            seen_post.append(payload)
            return 200, {
                "created": False,
                "replayed": True,
                "dispatch": None,
                "item": {"id": item_id},
            }
        if method == "GET" and path == f"/v1/work-items/{item_id}":
            return 200, {
                "item": {
                    "id": item_id,
                    "correlation_id": m.HISTORICAL_CORRELATION_ID,
                    "task_type": m.TASK_TYPE,
                    "status": "BLOQUEADO",
                    "last_error": "MaintenanceError:runner_service_not_found",
                    "attempts": 1,
                }
            }
        raise AssertionError((method, path))

    result = m.diagnose(
        confirm=m.CONFIRM,
        evidence_file=tmp_path / "evidence.json",
        requester=requester,
        source_host="Noteri",
        platform="nt",
    )

    assert seen_post == [body]
    assert result["idempotent_replay_used"] is True
    assert result["redispatch_performed"] is False
    assert result["physical_recovery_repeated"] is False


def test_non_replay_fails_closed() -> None:
    def requester(method, path, payload=None, *, timeout_seconds=5.0):
        if method == "POST" and path == "/v1/intake":
            return 201, {"replayed": False, "dispatch": {"worker": {}}}
        raise AssertionError((method, path))

    with pytest.raises(m.DiagnosticError, match="historical_replay_would_mutate"):
        m.replay_lookup(requester)


def test_error_shape_is_sanitized() -> None:
    assert m.sanitize_error("MaintenanceError:runner_service_not_found") == (
        "MaintenanceError:runner_service_not_found"
    )
    assert m.sanitize_error("secret=<token>") == "non_allowlisted_error_shape"
