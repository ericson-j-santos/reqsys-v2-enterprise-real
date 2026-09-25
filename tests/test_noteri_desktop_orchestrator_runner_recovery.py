from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import noteri_desktop_orchestrator_runner_recovery as recovery


def _worker(*, capability: bool = True) -> dict:
    safe = [recovery.TASK_TYPE] if capability else ["orchestrator.selftest"]
    return {
        "worker_id": "desktop-pdqk954",
        "device_name": recovery.TARGET_HOST,
        "fresh": True,
        "controller_online": True,
        "auth_valid": True,
        "profile": "NORMAL",
        "controller_version": "0.2.51",
        "capabilities": {
            "safe_task_types": safe,
            "dispatch_priority": 10,
        },
    }


class FakeControlPlane:
    def __init__(self, *, capability: bool = True, replay_ok: bool = True) -> None:
        self.worker = _worker(capability=capability)
        self.replay_ok = replay_ok
        self.posts = 0
        self.item_id = "item-runner-recovery-1"
        self.body: dict | None = None

    def __call__(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> tuple[int, dict]:
        if method == "GET" and path == "/readyz":
            return 200, {"ok": True, "ready": True}
        if method == "GET" and path == "/v1/workers":
            return 200, {"workers": [self.worker]}
        if method == "GET" and path.startswith("/v1/work-items/negative-"):
            return 404, {"error": "work_item_not_found"}
        if method == "POST" and path == "/v1/intake":
            self.posts += 1
            self.body = payload
            item = {
                "id": self.item_id,
                "status": "CONCLUÍDO",
                "result": {
                    "handler": recovery.TASK_TYPE,
                    "host": recovery.TARGET_HOST,
                    "mode": "scheduled_task",
                    "result": "recovered",
                    "started": True,
                },
            }
            if self.posts == 1:
                return 201, {
                    "created": True,
                    "replayed": False,
                    "item": item,
                    "dispatch": {"worker": self.worker},
                }
            return 200, {
                "created": False,
                "replayed": self.replay_ok,
                "item": item,
                "dispatch": None,
            }
        if method == "GET" and path == f"/v1/work-items/{self.item_id}":
            return 200, {
                "item": {
                    "id": self.item_id,
                    "status": "CONCLUÍDO",
                    "result": {
                        "handler": recovery.TASK_TYPE,
                        "host": recovery.TARGET_HOST,
                        "mode": "scheduled_task",
                        "result": "recovered",
                        "started": True,
                    },
                }
            }
        raise AssertionError((method, path, payload))


def test_recovery_contract_is_fixed() -> None:
    assert recovery.EXPECTED_SOURCE_HOST == "Noteri"
    assert recovery.TARGET_HOST == "DESKTOP-PDQK954"
    assert recovery.CONTROL_PLANE_PORT == 8787
    assert recovery.TASK_TYPE == "host.github_runner.recover.v1"


def test_source_host_fails_closed() -> None:
    recovery.validate_source_host("Noteri", "nt")
    with pytest.raises(recovery.RecoveryError, match="source_host_not_authorized"):
        recovery.validate_source_host("DESKTOP-PDQK954", "nt")
    with pytest.raises(recovery.RecoveryError, match="windows_required"):
        recovery.validate_source_host("Noteri", "posix")


def test_worker_must_advertise_recovery_capability() -> None:
    requester = FakeControlPlane(capability=False)
    with pytest.raises(
        recovery.RecoveryError,
        match="desktop_worker_recovery_capability_missing",
    ):
        recovery.require_desktop_worker(requester)


def test_positive_recovery_replay_and_independent_readback(tmp_path: Path) -> None:
    requester = FakeControlPlane()
    evidence = tmp_path / "evidence.json"

    result = recovery.recover(
        confirm=recovery.CONFIRM,
        correlation_id="runner-recovery-test-001",
        evidence_file=evidence,
        requester=requester,
        source_host="Noteri",
        platform="nt",
        sleep_fn=lambda _seconds: None,
    )

    assert result["ok"] is True
    assert result["recovery_result"] == "recovered"
    assert result["replay_idempotent"] is True
    assert result["negative_read_control"] is True
    assert result["independent_readback"] is True
    assert requester.posts == 2
    assert requester.body is not None
    assert requester.body["task_type"] == recovery.TASK_TYPE
    assert requester.body["payload"] == {
        "target_host": recovery.TARGET_HOST,
        "worker_hint": "builder",
    }
    assert requester.body["risk"] == 2
    written = evidence.read_text(encoding="utf-8")
    assert "DESKTOP_GITHUB_RUNNER_RECOVERY_COMPLETED" in written
    assert "token" not in written.casefold()


def test_replay_must_be_idempotent(tmp_path: Path) -> None:
    requester = FakeControlPlane(replay_ok=False)
    with pytest.raises(
        recovery.RecoveryError,
        match="runner_recovery_replay_not_idempotent",
    ):
        recovery.recover(
            confirm=recovery.CONFIRM,
            correlation_id="runner-recovery-test-002",
            evidence_file=tmp_path / "evidence.json",
            requester=requester,
            source_host="Noteri",
            platform="nt",
            sleep_fn=lambda _seconds: None,
        )


def test_workflow_uses_governed_noteri_session_and_gateway() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "noteri-desktop-orchestrator-runner-recovery.yml"
    ).read_text(encoding="utf-8")

    assert "881d9ca2f8e77025edb7298b22981109c567a730" in workflow
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in workflow
    assert "session_launcher.py" in workflow
    assert "command_gateway.py" in workflow
    assert "SESSION_LAUNCH_OK" in workflow
    assert "state_validated" in workflow
    assert '"--risk", "2"' in workflow
    assert "RECOVER-DESKTOP-GITHUB-RUNNER-VIA-ORCHESTRATOR" in workflow
    assert "scripts/noteri_desktop_orchestrator_runner_recovery.py" in workflow
    assert "python scripts/noteri_desktop_orchestrator_runner_recovery.py" not in workflow
    assert "production_touched" in workflow
    assert "reboot_performed" in workflow
