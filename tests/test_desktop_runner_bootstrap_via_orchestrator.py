from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import desktop_runner_bootstrap_via_orchestrator as subject


def test_rejects_non_noteri_source(tmp_path: Path) -> None:
    with pytest.raises(subject.BootstrapError, match="source_host_not_allowed"):
        subject.execute(
            confirm=subject.CONFIRM,
            correlation_id="corr-test",
            timeout_seconds=30,
            evidence_file=tmp_path / "evidence.json",
            source_host="OTHER-HOST",
            platform="nt",
        )


def test_worker_preflight_allows_governed_refresh_before_bootstrap() -> None:
    responses = [
        (200, {"ok": True, "ready": True}),
        (
            200,
            {
                "workers": {
                    "workers": [
                        {
                            "worker_id": subject.TARGET_WORKER,
                            "device_name": subject.TARGET_HOST,
                            "fresh": True,
                            "eligible": True,
                            "controller_version": "0.2.53",
                            "capabilities": {
                                "recovery_contract_version": 1,
                                "safe_task_types": [
                                    "host.inventory.files.v1",
                                    subject.REFRESH_TASK_TYPE,
                                ],
                            },
                        }
                    ]
                }
            },
        ),
    ]
    with patch.object(subject, "request_json", side_effect=responses):
        snapshot = subject.worker_preflight(require_bootstrap=False)

    assert snapshot["capability_present"] is False
    assert snapshot["refresh_capability_present"] is True


def test_worker_preflight_rejects_runtime_without_refresh_capability() -> None:
    responses = [
        (200, {"ok": True, "ready": True}),
        (
            200,
            {
                "workers": {
                    "workers": [
                        {
                            "worker_id": subject.TARGET_WORKER,
                            "device_name": subject.TARGET_HOST,
                            "fresh": True,
                            "eligible": True,
                            "controller_version": "0.2.53",
                            "capabilities": {
                                "recovery_contract_version": 1,
                                "safe_task_types": ["host.inventory.files.v1"],
                            },
                        }
                    ]
                }
            },
        ),
    ]
    with patch.object(subject, "request_json", side_effect=responses):
        with pytest.raises(subject.BootstrapError, match="refresh_capability_missing"):
            subject.worker_preflight(require_bootstrap=False)


def test_execute_proves_terminal_result_and_replay(tmp_path: Path) -> None:
    item_id = "11111111-1111-4111-8111-111111111111"
    preflight = {
        "worker_id": subject.TARGET_WORKER,
        "device_name": subject.TARGET_HOST,
        "controller_version": "0.2.53",
        "recovery_contract_version": 1,
        "fresh": True,
        "eligible": True,
        "capability_present": True,
        "refresh_capability_present": True,
    }
    first = {
        "item": {"id": item_id, "status": "EM ANDAMENTO"},
        "dispatch": {"worker": {"worker_id": subject.TARGET_WORKER}},
        "replayed": False,
    }
    terminal = {
        "item": {
            "id": item_id,
            "status": "CONCLUÍDO",
            "last_error": None,
            "result": {
                "handler": subject.TASK_TYPE,
                "host": subject.TARGET_HOST,
                "worker_id": subject.TARGET_WORKER,
                "runner_home": r"C:\actions-runner",
                "listener_pid": 4242,
                "local_listener_verified": True,
                "pickup_required": True,
                "github_connectivity_verified": False,
                "production_touched": False,
                "secrets_read": False,
            },
        }
    }
    replay = {
        "item": {"id": item_id, "status": "CONCLUÍDO"},
        "dispatch": None,
        "replayed": True,
    }
    with (
        patch.object(subject, "worker_preflight", return_value=preflight),
        patch.object(
            subject,
            "request_json",
            side_effect=[(201, first), (200, terminal), (200, replay)],
        ),
    ):
        result = subject.execute(
            confirm=subject.CONFIRM,
            correlation_id="corr-test-123",
            timeout_seconds=30,
            evidence_file=tmp_path / "evidence.json",
            source_host=subject.EXPECTED_SOURCE_HOST,
            platform="nt",
        )

    assert result["ok"] is True
    assert result["result"] == "DESKTOP_GITHUB_RUNNER_LOCAL_BOOTSTRAP_VERIFIED"
    assert result["bootstrap"]["local_listener_verified"] is True
    assert result["replay"] == {
        "replayed": True,
        "same_work_item": True,
        "redispatched": False,
    }
    persisted = (tmp_path / "evidence.json").read_text(encoding="utf-8")
    assert "corr-test-123" in persisted


def test_validate_result_rejects_false_success() -> None:
    with pytest.raises(subject.BootstrapError, match="result_invalid"):
        subject.validate_result(
            {
                "status": "CONCLUÍDO",
                "result": {
                    "handler": subject.TASK_TYPE,
                    "host": subject.TARGET_HOST,
                    "worker_id": subject.TARGET_WORKER,
                    "local_listener_verified": False,
                    "pickup_required": True,
                    "github_connectivity_verified": False,
                    "production_touched": False,
                    "secrets_read": False,
                },
            }
        )


def test_execute_refreshes_runtime_before_bootstrap(tmp_path: Path) -> None:
    item_id = "22222222-2222-4222-8222-222222222222"
    before = {
        "worker_id": subject.TARGET_WORKER,
        "device_name": subject.TARGET_HOST,
        "controller_version": "0.2.53",
        "recovery_contract_version": 1,
        "fresh": True,
        "eligible": True,
        "capability_present": False,
        "refresh_capability_present": True,
    }
    after = {**before, "capability_present": True}
    first = {
        "item": {"id": item_id, "status": "EM ANDAMENTO"},
        "dispatch": {"worker": {"worker_id": subject.TARGET_WORKER}},
        "replayed": False,
    }
    terminal = {
        "item": {
            "id": item_id,
            "status": "CONCLUÍDO",
            "result": {
                "handler": subject.TASK_TYPE,
                "host": subject.TARGET_HOST,
                "worker_id": subject.TARGET_WORKER,
                "local_listener_verified": True,
                "pickup_required": True,
                "github_connectivity_verified": False,
                "production_touched": False,
                "secrets_read": False,
            },
        }
    }
    replay = {
        "item": {"id": item_id, "status": "CONCLUÍDO"},
        "dispatch": None,
        "replayed": True,
    }
    refresh = {
        "required": True,
        "performed": True,
        "target_sha": subject.ORCHESTRATOR_BOOTSTRAP_SHA,
        "work_item_id": "33333333-3333-4333-8333-333333333333",
    }

    with (
        patch.object(subject, "worker_preflight", return_value=before),
        patch.object(
            subject,
            "refresh_runtime_for_bootstrap",
            return_value=refresh,
        ) as refresh_call,
        patch.object(subject, "wait_for_bootstrap_capability", return_value=after),
        patch.object(
            subject,
            "request_json",
            side_effect=[(201, first), (200, terminal), (200, replay)],
        ),
    ):
        result = subject.execute(
            confirm=subject.CONFIRM,
            correlation_id="corr-refresh-test",
            timeout_seconds=30,
            evidence_file=tmp_path / "evidence.json",
            source_host=subject.EXPECTED_SOURCE_HOST,
            platform="nt",
        )

    refresh_call.assert_called_once()
    assert result["runtime_refresh"]["performed"] is True
    assert result["preflight"]["capability_present"] is True


def test_work_item_id_rejects_path_injection() -> None:
    with pytest.raises(subject.BootstrapError, match="work_item_id_invalid"):
        subject.validate_work_item_id("../../v1/status")
