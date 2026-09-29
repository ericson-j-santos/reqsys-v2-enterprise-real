from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "noteri_desktop_orchestrator_status_probe.py"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-desktop-network-probe.yml"

SPEC = importlib.util.spec_from_file_location("noteri_desktop_orchestrator_status_probe", SCRIPT)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_contract_is_fixed_and_read_only() -> None:
    assert probe.EXPECTED_SOURCE_HOST == "Noteri"
    assert probe.TARGET_HOST == "DESKTOP-PDQK954"
    assert probe.ENDPOINT == "http://DESKTOP-PDQK954:8787"
    assert probe.TARGET_WORKER == "desktop-pdqk954"
    assert probe.TARGET_RUNTIME_SHA == "313f5da4bb0ee9dd70937c238c7cfdf4e3514602"
    assert probe.RECOVERY_CORRELATION_PREFIX == "desktop-runner-orchestrator-"

    source = SCRIPT.read_text(encoding="utf-8")
    assert 'method="GET"' in source
    assert "/readyz" in source
    assert "/v1/status" in source
    assert "subprocess" not in source
    assert "shell=True" not in source
    assert 'parser.add_argument("--host"' not in source
    assert 'parser.add_argument("--url"' not in source


def test_positive_readback_is_sanitized_and_current(monkeypatch) -> None:
    monkeypatch.setattr(probe, "require_noteri", lambda: None)

    def fake_request(path: str, timeout_seconds: float):
        assert timeout_seconds == 5.0
        if path == "/readyz":
            return 200, {"ready": True}
        assert path == "/v1/status"
        return 200, {
            "workers": {
                "workers": [
                    {
                        "worker_id": "desktop-pdqk954",
                        "device_name": "DESKTOP-PDQK954",
                        "fresh": True,
                        "eligible": True,
                        "controller_version": "current",
                        "profile": "NORMAL",
                        "capabilities": {
                            "recovery_contract_version": "1",
                            "safe_task_types": [
                                "host.orchestrator.refresh.v1",
                                "host.github_runner.bootstrap.v1",
                                "host.github_runner.recover.v1",
                            ],
                            "runtime_source_sha": probe.TARGET_RUNTIME_SHA,
                            "worker_instance_id": "worker-current-1",
                        },
                    }
                ]
            }
        }

    monkeypatch.setattr(probe, "request_json", fake_request)
    result = probe.probe(
        confirm=probe.CONFIRM,
        correlation_id="desktop-status-current-001",
        timeout_seconds=5.0,
    )

    assert result["ok"] is True
    assert result["probe_completed"] is True
    assert result["ready"] is True
    assert result["worker_match_count"] == 1
    assert result["runtime_identity_current"] is True
    assert result["latest_runner_recovery_blocker"] is None
    assert result["refresh_capability_present"] is True
    assert result["bootstrap_capability_present"] is True
    assert "host.github_runner.recover.v1" in result["safe_task_types"]
    assert result["remote_shell_used"] is False
    assert result["credentials_supplied"] is False
    assert result["secrets_read"] is False
    assert result["production_touched"] is False
    assert "workers" not in result



def test_latest_runner_recovery_blocker_is_sanitized(monkeypatch) -> None:
    monkeypatch.setattr(probe, "require_noteri", lambda: None)

    def fake_request(path: str, timeout_seconds: float):
        if path == "/readyz":
            return 200, {"ready": True}
        return 200, {
            "workers": {"workers": []},
            "blockers": [
                {
                    "id": "work-1",
                    "correlation_id": "desktop-runner-orchestrator-36637195975-1",
                    "target_worker": "builder",
                    "attempts": 1,
                    "last_error": (
                        "MaintenanceError: registered github runner home invalid; "
                        "missing: C:\\Users\\erics\\runner\\.runner"
                    ),
                },
                {
                    "id": "other",
                    "correlation_id": "unrelated-control-plane-1",
                    "attempts": 2,
                    "last_error": "unrelated",
                },
            ],
        }

    monkeypatch.setattr(probe, "request_json", fake_request)
    result = probe.probe(
        confirm=probe.CONFIRM,
        correlation_id="desktop-status-blocker-001",
        timeout_seconds=5.0,
    )

    blocker = result["latest_runner_recovery_blocker"]
    assert blocker["work_item_id"] == "work-1"
    assert blocker["correlation_id"] == "desktop-runner-orchestrator-36637195975-1"
    assert blocker["attempts"] == 1
    assert "MaintenanceError" in blocker["last_error"]
    assert "C:\\Users" not in blocker["last_error"]
    assert "<path>" in blocker["last_error"]


def test_duplicate_worker_is_not_accepted_as_identity(monkeypatch) -> None:
    monkeypatch.setattr(probe, "require_noteri", lambda: None)
    duplicate = {
        "worker_id": "desktop-pdqk954",
        "capabilities": {
            "safe_task_types": ["host.github_runner.recover.v1"],
            "runtime_source_sha": probe.TARGET_RUNTIME_SHA,
            "worker_instance_id": "duplicate",
        },
    }

    def fake_request(path: str, timeout_seconds: float):
        if path == "/readyz":
            return 200, {"ready": True}
        return 200, {"workers": {"workers": [duplicate, duplicate]}}

    monkeypatch.setattr(probe, "request_json", fake_request)
    result = probe.probe(
        confirm=probe.CONFIRM,
        correlation_id="desktop-status-duplicate-001",
        timeout_seconds=5.0,
    )

    assert result["worker_match_count"] == 2
    assert result["worker_id"] is None
    assert result["runtime_identity_current"] is False
    assert result["safe_task_types"] == []


def test_unreachable_endpoint_does_not_become_successful_identity(monkeypatch) -> None:
    monkeypatch.setattr(probe, "require_noteri", lambda: None)
    monkeypatch.setattr(probe, "request_json", lambda path, timeout: (None, {}))

    result = probe.probe(
        confirm=probe.CONFIRM,
        correlation_id="desktop-status-offline-001",
        timeout_seconds=5.0,
    )

    assert result["probe_completed"] is True
    assert result["ready"] is False
    assert result["status_http_status"] is None
    assert result["worker_match_count"] == 0
    assert result["runtime_identity_current"] is False


def test_workflow_uses_pinned_portable_python_for_status_job() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/noteri_desktop_orchestrator_status_probe.py" in raw
    assert "tests/test_noteri_desktop_orchestrator_status_probe.py" in raw
    assert '"fix/noteri-desktop-orchestrator-status-*"' in raw
    assert "!startsWith(github.ref_name, 'fix/noteri-desktop-orchestrator-status-')" in raw
    status_block = raw.split("  orchestrator_status_readback:", 1)[1]
    assert "python-3.12.10-embed-amd64.zip" in status_block
    assert "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3" in status_block
    assert "$raw = & $env:REQSYS_PYTHON $launcher @args" in status_block
    assert "& $env:REQSYS_PYTHON $gateway @args" in status_block
    assert "actions/setup-python@" not in status_block
    assert status_block.count('"--risk", "2"') == 1
