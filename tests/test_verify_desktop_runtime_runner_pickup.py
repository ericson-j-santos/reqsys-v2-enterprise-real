from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "verify_desktop_runtime_runner_pickup.py"
SPEC = importlib.util.spec_from_file_location("verify_desktop_runtime_runner_pickup", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_contract_is_fixed() -> None:
    assert m.TARGET_REPOSITORY == "ericson-j-santos/desktop-pc24x7-runtime"
    assert m.TARGET_SHA == "4f71186f3c7636ad80f8bd14c74e3fded28101ec"
    assert m.TARGET_WORKFLOW == "desktop-rdc-recovery.yml"


def test_dispatch_uses_fixed_main_ref_and_no_arbitrary_inputs() -> None:
    seen = {}

    def sender(request):
        seen["url"] = request.full_url
        seen["data"] = request.data.decode("utf-8")
        seen["authorization"] = request.get_header("Authorization")
        return 204

    m.dispatch("secret-value", sender=sender)
    assert seen["url"].endswith(
        "/repos/ericson-j-santos/desktop-pc24x7-runtime/actions/workflows/"
        "desktop-rdc-recovery.yml/dispatches"
    )
    assert seen["data"] == '{"ref": "main"}'
    assert seen["authorization"] == "Bearer secret-value"
    assert "secret-value" not in seen["url"]
    assert "secret-value" not in seen["data"]


def test_find_new_run_rejects_old_or_wrong_sha() -> None:
    runs = [
        {"id": 10, "event": "workflow_dispatch", "head_sha": m.TARGET_SHA},
        {"id": 11, "event": "workflow_dispatch", "head_sha": "0" * 40},
        {"id": 12, "event": "push", "head_sha": m.TARGET_SHA},
        {"id": 13, "event": "workflow_dispatch", "head_sha": m.TARGET_SHA},
    ]
    selected = m.find_new_run(runs, before_ids={10})
    assert selected is not None
    assert selected["id"] == 13


def test_verify_pickup_requires_exact_target_main(monkeypatch) -> None:
    monkeypatch.setattr(m, "current_main_sha", lambda token, requester=m.request_json: "0" * 40)
    with pytest.raises(m.PickupError, match="target_main_sha_mismatch"):
        m.verify_pickup(
            "secret",
            requester=lambda request: {},
            sender=lambda request: 204,
            timeout_seconds=0.01,
            poll_seconds=0.0,
        )


def test_verify_pickup_accepts_only_new_successful_run(monkeypatch) -> None:
    monkeypatch.setattr(m, "current_main_sha", lambda token, requester=m.request_json: m.TARGET_SHA)
    calls = {"runs": 0, "dispatch": 0}

    def fake_runs(token, requester=m.request_json):
        calls["runs"] += 1
        if calls["runs"] == 1:
            return [{"id": 100, "event": "workflow_dispatch", "head_sha": m.TARGET_SHA}]
        if calls["runs"] == 2:
            return [
                {"id": 100, "event": "workflow_dispatch", "head_sha": m.TARGET_SHA},
                {
                    "id": 101,
                    "event": "workflow_dispatch",
                    "head_sha": m.TARGET_SHA,
                    "status": "in_progress",
                    "conclusion": None,
                    "html_url": "https://github.com/example/run/101",
                },
            ]
        return [
            {
                "id": 101,
                "event": "workflow_dispatch",
                "head_sha": m.TARGET_SHA,
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.com/example/run/101",
            }
        ]

    monkeypatch.setattr(m, "workflow_runs", fake_runs)
    monkeypatch.setattr(
        m,
        "dispatch",
        lambda token, sender=m.send_status: calls.update({"dispatch": calls["dispatch"] + 1}),
    )

    result = m.verify_pickup(
        "secret",
        requester=lambda request: {},
        sender=lambda request: 204,
        timeout_seconds=1,
        poll_seconds=0,
    )
    assert result["ok"] is True
    assert result["run_id"] == 101
    assert result["conclusion"] == "success"
    assert calls["dispatch"] == 1


def test_completed_failure_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(m, "current_main_sha", lambda token, requester=m.request_json: m.TARGET_SHA)
    monkeypatch.setattr(
        m,
        "workflow_runs",
        lambda token, requester=m.request_json: [
            {
                "id": 202,
                "event": "workflow_dispatch",
                "head_sha": m.TARGET_SHA,
                "status": "completed",
                "conclusion": "failure",
            }
        ],
    )
    monkeypatch.setattr(m, "dispatch", lambda token, sender=m.send_status: None)

    calls = {"n": 0}

    def runs_with_before(token, requester=m.request_json):
        calls["n"] += 1
        if calls["n"] == 1:
            return []
        return [
            {
                "id": 202,
                "event": "workflow_dispatch",
                "head_sha": m.TARGET_SHA,
                "status": "completed",
                "conclusion": "failure",
            }
        ]

    monkeypatch.setattr(m, "workflow_runs", runs_with_before)
    with pytest.raises(m.PickupError, match="target_workflow_failed:failure"):
        m.verify_pickup(
            "secret",
            requester=lambda request: {},
            sender=lambda request: 204,
            timeout_seconds=1,
            poll_seconds=0,
        )
