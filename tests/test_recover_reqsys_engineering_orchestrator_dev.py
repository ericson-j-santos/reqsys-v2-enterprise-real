from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "recover_reqsys_engineering_orchestrator_dev.py"

spec = importlib.util.spec_from_file_location("recover_reqsys_engineering_orchestrator_dev", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_recovery_is_fixed_to_desktop_dev_and_existing_task():
    assert module.EXPECTED_HOST == "DESKTOP-PDQK954"
    assert module.CONTROL_PLANE == "http://127.0.0.1:8787"
    assert module.TASK_NAME == r"\Automation\ReqSysOrchestrator24x7"
    assert module.CONFIRM == "RECOVER-REQSYS-ENGINEERING-ORCHESTRATOR-DEV"


def test_healthy_runtime_does_not_run_task(tmp_path):
    calls = []

    result = module.recover(
        confirm=module.CONFIRM,
        evidence_path=tmp_path / "evidence.json",
        host=module.EXPECTED_HOST,
        platform="nt",
        timeout_seconds=1,
        ready_probe=lambda: True,
        worker_probe=lambda: {
            "reachable": True,
            "http_status": 200,
            "payload_valid": True,
            "match_count": 1,
            "operational": True,
            "noteri": {
                "fresh": True,
                "controller_online": True,
                "auth_valid": True,
                "profile": "NORMAL",
                "operational": True,
            },
        },
        task_runner=lambda: calls.append("run") or 0,
        sleep_fn=lambda _: None,
    )

    assert result["ok"] is True
    assert result["recovery_attempted"] is False
    assert calls == []
    assert result["production_touched"] is False
    assert result["secrets_read"] is False


def test_unready_runtime_runs_existing_task_and_waits_for_noteri(tmp_path):
    ready_values = iter([False, False, True])
    worker_values = iter([
        {"operational": False},
        {"operational": False},
        {
            "reachable": True,
            "http_status": 200,
            "payload_valid": True,
            "match_count": 1,
            "operational": True,
            "noteri": {
                "fresh": True,
                "controller_online": True,
                "auth_valid": True,
                "profile": "NORMAL",
                "operational": True,
            },
        },
    ])
    calls = []

    result = module.recover(
        confirm=module.CONFIRM,
        evidence_path=tmp_path / "evidence.json",
        host=module.EXPECTED_HOST,
        platform="nt",
        timeout_seconds=1,
        ready_probe=lambda: next(ready_values),
        worker_probe=lambda: next(worker_values),
        task_runner=lambda: calls.append("run") or 0,
        sleep_fn=lambda _: None,
    )

    assert result["ok"] is True
    assert result["recovery_attempted"] is True
    assert result["recovery_method"] == "existing_scheduled_task"
    assert calls == ["run"]
    assert json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))["ok"] is True


def test_task_start_failure_fails_closed(tmp_path):
    with pytest.raises(module.RecoveryError, match="orchestrator_task_start_failed"):
        module.recover(
            confirm=module.CONFIRM,
            evidence_path=tmp_path / "evidence.json",
            host=module.EXPECTED_HOST,
            platform="nt",
            timeout_seconds=1,
            ready_probe=lambda: False,
            worker_probe=lambda: {"operational": False},
            task_runner=lambda: 5,
            sleep_fn=lambda _: None,
        )


def test_wrong_host_is_rejected_before_task_start(tmp_path):
    calls = []
    with pytest.raises(module.RecoveryError, match="host_not_authorized"):
        module.recover(
            confirm=module.CONFIRM,
            evidence_path=tmp_path / "evidence.json",
            host="other-host",
            platform="nt",
            timeout_seconds=1,
            ready_probe=lambda: False,
            worker_probe=lambda: {"operational": False},
            task_runner=lambda: calls.append("run") or 0,
            sleep_fn=lambda _: None,
        )
    assert calls == []


def test_worker_probe_exposes_only_allowlisted_state(monkeypatch):
    monkeypatch.setattr(
        module,
        "_get_json",
        lambda path: (
            200,
            {
                "workers": [
                    {
                        "worker_id": "secret-id",
                        "device_name": "Noteri",
                        "fresh": True,
                        "controller_online": True,
                        "auth_valid": True,
                        "profile": "ESTUDO",
                        "token": "must-not-leak",
                    }
                ]
            },
        ),
    )

    result = module.probe_noteri_worker()
    rendered = json.dumps(result, sort_keys=True)

    assert result["operational"] is True
    assert result["noteri"]["profile"] == "ESTUDO"
    assert "secret-id" not in rendered
    assert "must-not-leak" not in rendered
