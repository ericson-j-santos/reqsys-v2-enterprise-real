from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from scripts import recover_noteri_installed_orchestrator_worker as m

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-installed-orchestrator-worker-recovery.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"


def _installed_runtime(root: Path) -> Path:
    install = root / "runtime"
    (install / "orchestrator").mkdir(parents=True)
    (install / "scripts").mkdir()
    (install / "orchestrator" / "maintenance.py").write_text(
        'PROFILE_SET_TASK = "host.profile.set.v1"\n',
        encoding="utf-8",
    )
    (install / "orchestrator" / "worker_agent.py").write_text(
        "PROFILE_SET_TASK = 'host.profile.set.v1'\ndef safe_task_types(): return [PROFILE_SET_TASK]\n",
        encoding="utf-8",
    )
    (install / "scripts" / "install_windows_autostart.py").write_text(
        "def start_supervisor(*args): return 1234\n",
        encoding="utf-8",
    )
    (install / "service-config.json").write_text(
        json.dumps({"mode": "worker"}),
        encoding="utf-8",
    )
    (install / "worker-config.json").write_text(
        json.dumps({"worker_id": "noteri", "endpoint": m.CONTROL_PLANE}),
        encoding="utf-8",
    )
    return install


def _operational_state() -> dict:
    return {
        "reachable": True,
        "http_status": 200,
        "payload_valid": True,
        "match_count": 1,
        "operational": True,
        "profile_task_capable": True,
        "noteri": {
            "fresh": True,
            "controller_online": True,
            "auth_valid": True,
            "profile": "NORMAL",
        },
    }


def test_contract_accepts_only_fixed_installed_worker(tmp_path: Path) -> None:
    install = _installed_runtime(tmp_path)
    contract = m.inspect_installed_contract(install)
    assert contract["service_mode"] == "worker"
    assert contract["worker_id"] == "noteri"
    assert contract["endpoint"] == "http://DESKTOP-PDQK954:8787"
    assert contract["profile_capability_code_present"] is True


def test_contract_fails_closed_without_profile_capability(tmp_path: Path) -> None:
    install = _installed_runtime(tmp_path)
    (install / "orchestrator" / "maintenance.py").write_text("# old runtime\n", encoding="utf-8")
    with pytest.raises(m.RecoveryError, match="installed_profile_capability_code_missing"):
        m.inspect_installed_contract(install)


def test_worker_state_is_sanitized() -> None:
    def fake_get(_path):
        return 200, {
            "workers": [
                {
                    "worker_id": "noteri",
                    "device_name": "Noteri",
                    "fresh": True,
                    "controller_online": True,
                    "auth_valid": True,
                    "profile": "NORMAL",
                    "token": "must-not-leak",
                    "capabilities": {
                        "safe_task_types": ["host.profile.set.v1"],
                        "secret": "must-not-leak",
                    },
                }
            ]
        }

    state = m.worker_state(fake_get)
    rendered = json.dumps(state, sort_keys=True)
    assert state["operational"] is True
    assert state["profile_task_capable"] is True
    assert "must-not-leak" not in rendered
    assert "token" not in rendered
    assert "secret" not in rendered


def test_recover_requires_sha_and_independent_operational_readback(tmp_path: Path) -> None:
    sha = "a" * 40
    evidence = tmp_path / "evidence.json"
    result = m.recover(
        confirm=m.CONFIRM,
        source_root=tmp_path,
        expected_workflow_sha=sha,
        evidence_path=evidence,
        timeout_seconds=1,
        host="Noteri",
        platform="nt",
        sha_fn=lambda _: sha,
        contract_fn=lambda: {
            "service_mode": "worker",
            "worker_id": "noteri",
            "endpoint": m.CONTROL_PLANE,
            "profile_capability_code_present": True,
            "runtime_source_sha": None,
        },
        start_fn=lambda _: 4321,
        state_fn=_operational_state,
        sleep_fn=lambda _: None,
    )
    assert result["ok"] is True
    assert result["workflow_sha_verified"] is True
    assert result["after"]["operational"] is True
    assert result["after"]["profile_task_capable"] is True
    assert result["runner_tracking_removed_before_start"] is True
    assert result["task_scheduler_modified"] is False
    assert result["production_touched"] is False
    assert result["secrets_read"] is False
    assert result["rdc_required"] is False


def test_wrong_host_fails_before_start(tmp_path: Path) -> None:
    with pytest.raises(m.RecoveryError, match="host_not_authorized"):
        m.recover(
            confirm=m.CONFIRM,
            source_root=tmp_path,
            expected_workflow_sha="a" * 40,
            evidence_path=tmp_path / "evidence.json",
            timeout_seconds=1,
            host="DESKTOP-PDQK954",
            platform="nt",
            sha_fn=lambda _: "a" * 40,
            contract_fn=lambda: pytest.fail("contract must not be inspected"),
            start_fn=lambda _: pytest.fail("supervisor must not start"),
            state_fn=_operational_state,
            sleep_fn=lambda _: None,
        )


def test_workflow_is_owner_only_noteri_and_not_pull_request() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in workflow
    assert "github.repository == 'ericson-j-santos/reqsys-v2-enterprise-real'" in workflow
    assert "github.actor == 'ericson-j-santos'" in workflow
    assert "pull_request:" not in workflow
    assert "persist-credentials: false" in workflow
    assert "--confirm RECOVER-NOTERI-INSTALLED-ORCHESTRATOR-WORKER-DEV" in workflow
    assert "production_touched" in workflow
    assert "secrets_read" in workflow
    assert "rdc_required" in workflow


def test_self_hosted_policy_allowlists_recovery_workflow() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert ".github/workflows/noteri-installed-orchestrator-worker-recovery.yml" in policy[
        "approved_workflows"
    ]
