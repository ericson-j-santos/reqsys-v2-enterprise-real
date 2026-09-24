from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "noteri_desktop_runner_scm_recovery.py"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-desktop-runner-scm-recovery.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"

SPEC = importlib.util.spec_from_file_location("noteri_desktop_runner_scm_recovery", SCRIPT)
assert SPEC and SPEC.loader
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


class FakeBackend:
    def __init__(self, candidates, outcome=None):
        self.candidates = candidates
        self.outcome = outcome or {
            "before_state": "stopped",
            "after_state": "running",
            "changed": True,
        }
        self.started = []

    def runner_candidates(self):
        return list(self.candidates)

    def ensure_running(self, service_name, timeout_seconds):
        self.started.append((service_name, timeout_seconds))
        return dict(self.outcome)


def test_recovery_starts_exact_single_runner() -> None:
    backend = FakeBackend(
        [
            {
                "service_name": "actions.runner.reqsys.desktop",
                "display_name": "GitHub Actions Runner",
                "state": "stopped",
            }
        ]
    )
    result = recovery.recover(
        recovery.CONFIRM,
        "corr-scm-recovery-1234",
        backend=backend,
        source_host="Noteri",
    )
    assert result["ok"] is True
    assert result["target_host"] == "DESKTOP-PDQK954"
    assert result["transport"] == "windows_scm_rpc"
    assert result["before_state"] == "stopped"
    assert result["after_state"] == "running"
    assert result["changed"] is True
    assert backend.started == [("actions.runner.reqsys.desktop", 20.0)]


def test_recovery_is_idempotent_when_already_running() -> None:
    backend = FakeBackend(
        [
            {
                "service_name": "actions.runner.reqsys.desktop",
                "display_name": "GitHub Actions Runner",
                "state": "running",
            }
        ],
        outcome={
            "before_state": "running",
            "after_state": "running",
            "changed": False,
        },
    )
    result = recovery.recover(
        recovery.CONFIRM,
        "corr-scm-idempotent-1234",
        backend=backend,
        source_host="noteri",
    )
    assert result["changed"] is False
    assert result["after_state"] == "running"


def test_missing_service_fails_closed() -> None:
    with pytest.raises(recovery.RecoveryError, match="runner_service_not_found"):
        recovery.recover(
            recovery.CONFIRM,
            "corr-scm-missing-1234",
            backend=FakeBackend([]),
            source_host="Noteri",
        )


def test_multiple_runner_services_fail_closed() -> None:
    candidates = [
        {"service_name": "actions.runner.one", "display_name": "GitHub Actions Runner 1", "state": "stopped"},
        {"service_name": "actions.runner.two", "display_name": "GitHub Actions Runner 2", "state": "stopped"},
    ]
    with pytest.raises(recovery.RecoveryError, match="runner_service_ambiguous"):
        recovery.recover(
            recovery.CONFIRM,
            "corr-scm-ambiguous-1234",
            backend=FakeBackend(candidates),
            source_host="Noteri",
        )


def test_request_and_source_are_fixed() -> None:
    with pytest.raises(recovery.RecoveryError, match="confirmation_invalid"):
        recovery.validate_request("NO", "corr-scm-invalid-1234")
    with pytest.raises(recovery.RecoveryError, match="source_host_not_authorized"):
        recovery.recover(
            recovery.CONFIRM,
            "corr-scm-source-1234",
            backend=FakeBackend([]),
            source_host="DESKTOP-PDQK954",
        )
    content = SCRIPT.read_text(encoding="utf-8")
    assert 'TARGET_HOST = "DESKTOP-PDQK954"' in content
    assert recovery.SCM_MACHINE == r"\\DESKTOP-PDQK954"
    assert recovery.SCM_MACHINE[2:] == "DESKTOP-PDQK954"
    assert len(recovery.SCM_MACHINE) == len("DESKTOP-PDQK954") + 2
    assert 'parser.add_argument("--target"' not in content
    assert "shell=True" not in content


def test_blocked_payload_is_sanitized() -> None:
    payload = recovery.blocked_payload(
        recovery.RecoveryError("scm_access_denied", winerror=5),
        "corr-scm-denied-1234",
    )
    assert payload["ok"] is False
    assert payload["error_code"] == "scm_access_denied"
    assert payload["winerror"] == 5
    assert "password" not in json.dumps(payload).casefold()
    assert payload["secrets_read"] is False
    assert payload["production_touched"] is False


def test_workflow_and_policy_are_noteri_only() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in content
    assert "--confirm RECOVER-NOTERI-DESKTOP-RUNNER-SCM" in content
    assert "workflow_dispatch:" in content
    assert "_rules\\scripts\\session_launcher.py" in content
    assert "_rules\\scripts\\command_gateway.py" in content
    assert '"--risk", "2"' in content
    assert '"--sync-ref", "origin/fix/noteri-desktop-runner-scm-recovery-20260924"' in content
    assert "inputs:" not in content
    assert "fix/noteri-desktop-runner-scm-recovery-*" in content
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert ".github/workflows/noteri-desktop-runner-scm-recovery.yml" in policy["approved_workflows"]
