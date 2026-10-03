from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "recover_reqsys_engineering_orchestrator_dev.py"

spec = importlib.util.spec_from_file_location(
    "recover_reqsys_engineering_orchestrator_dev",
    SCRIPT,
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def operational_worker(profile: str = "NORMAL"):
    return {
        "reachable": True,
        "http_status": 200,
        "payload_valid": True,
        "match_count": 1,
        "operational": True,
        "noteri": {
            "fresh": True,
            "controller_online": True,
            "auth_valid": True,
            "profile": profile,
            "operational": True,
        },
    }


def test_recovery_is_fixed_to_desktop_dev_and_existing_task():
    assert module.EXPECTED_HOST == "DESKTOP-PDQK954"
    assert module.CONTROL_PLANE == "http://127.0.0.1:8787"
    assert module.TASK_NAME == r"\Automation\ReqSysOrchestrator24x7"
    assert module.ORCHESTRATOR_INSTALL_ROOT == Path(
        r"C:\dev\chatgpt-workers\reqsys-orchestrator-24x7-runtime"
    )
    assert module.CONFIRM == "RECOVER-REQSYS-ENGINEERING-ORCHESTRATOR-DEV"


def test_healthy_runtime_does_not_run_recovery(tmp_path):
    calls = []

    result = module.recover(
        confirm=module.CONFIRM,
        evidence_path=tmp_path / "evidence.json",
        host=module.EXPECTED_HOST,
        platform="nt",
        timeout_seconds=1,
        ready_probe=lambda: True,
        worker_probe=operational_worker,
        task_runner=lambda: calls.append("task") or 0,
        supervisor_starter=lambda: calls.append("supervisor") or {"started": True},
        sleep_fn=lambda _: None,
    )

    assert result["ok"] is True
    assert result["recovery_attempted"] is False
    assert result["supervisor_fallback_used"] is False
    assert result["recovery_method"] == "not_required"
    assert calls == []


def test_unready_runtime_uses_existing_task_when_it_becomes_ready(tmp_path):
    state = {"ready_calls": 0}

    def ready_probe():
        state["ready_calls"] += 1
        return state["ready_calls"] >= 3

    calls = []
    result = module.recover(
        confirm=module.CONFIRM,
        evidence_path=tmp_path / "evidence.json",
        host=module.EXPECTED_HOST,
        platform="nt",
        timeout_seconds=1,
        ready_probe=ready_probe,
        worker_probe=operational_worker,
        task_runner=lambda: calls.append("task") or 0,
        supervisor_starter=lambda: calls.append("supervisor") or {"started": True},
        sleep_fn=lambda _: None,
    )

    assert result["ok"] is True
    assert result["recovery_attempted"] is True
    assert result["supervisor_fallback_used"] is False
    assert result["recovery_method"] == "existing_scheduled_task"
    assert calls == ["task"]


def test_fallback_starts_validated_supervisor_when_task_does_not_make_ready(tmp_path):
    state = {"supervisor_started": False}
    calls = []

    def ready_probe():
        return state["supervisor_started"]

    def supervisor_starter():
        calls.append("supervisor")
        state["supervisor_started"] = True
        return {
            "started": True,
            "pid_present": True,
            "tracking_marker_removed": True,
            "runtime_contract_validated": True,
        }

    result = module.recover(
        confirm=module.CONFIRM,
        evidence_path=tmp_path / "evidence.json",
        host=module.EXPECTED_HOST,
        platform="nt",
        timeout_seconds=1,
        ready_probe=ready_probe,
        worker_probe=operational_worker,
        task_runner=lambda: calls.append("task") or 0,
        supervisor_starter=supervisor_starter,
        sleep_fn=lambda _: None,
    )

    assert result["ok"] is True
    assert calls == ["task", "supervisor"]
    assert result["supervisor_fallback_used"] is True
    assert result["recovery_method"] == "scheduled_task_then_validated_supervisor"
    assert result["supervisor_start"]["runtime_contract_validated"] is True
    persisted = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    assert persisted["production_touched"] is False
    assert persisted["secrets_read"] is False


def test_validate_runtime_layout_accepts_only_control_plane_contract(tmp_path):
    root = tmp_path / "runtime"
    (root / "scripts").mkdir(parents=True)
    (root / "orchestrator").mkdir()
    (root / "scripts" / "service_supervisor.py").write_text("# ok\n", encoding="utf-8")
    (root / "orchestrator" / "__init__.py").write_text("", encoding="utf-8")
    worker_config = root / "worker-config.json"
    worker_config.write_text(
        json.dumps({
            "endpoint": module.CONTROL_PLANE,
            "worker_id": "desktop-pdqk954",
        }),
        encoding="utf-8",
    )
    service_config = root / "service-config.json"
    service_config.write_text(
        json.dumps({
            "mode": "control-plane-worker",
            "install_root": str(root),
            "port": 8787,
            "ready_url": module.CONTROL_PLANE + "/readyz",
            "worker_config": str(worker_config),
        }),
        encoding="utf-8",
    )

    layout = module.validate_runtime_layout(root)

    assert layout["root"] == root.resolve()
    assert layout["service_config"] == service_config.resolve()


def test_validate_runtime_layout_rejects_wrong_port(tmp_path):
    root = tmp_path / "runtime"
    (root / "scripts").mkdir(parents=True)
    (root / "orchestrator").mkdir()
    (root / "scripts" / "service_supervisor.py").write_text("# ok\n", encoding="utf-8")
    (root / "orchestrator" / "__init__.py").write_text("", encoding="utf-8")
    worker_config = root / "worker-config.json"
    worker_config.write_text(
        json.dumps({
            "endpoint": module.CONTROL_PLANE,
            "worker_id": "desktop-pdqk954",
        }),
        encoding="utf-8",
    )
    (root / "service-config.json").write_text(
        json.dumps({
            "mode": "control-plane-worker",
            "install_root": str(root),
            "port": 9999,
            "ready_url": module.CONTROL_PLANE + "/readyz",
            "worker_config": str(worker_config),
        }),
        encoding="utf-8",
    )

    with pytest.raises(module.RecoveryError, match="orchestrator_runtime_contract_invalid"):
        module.validate_runtime_layout(root)


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
            supervisor_starter=lambda: {"started": True},
            sleep_fn=lambda _: None,
        )


def test_wrong_host_is_rejected_before_recovery(tmp_path):
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
            task_runner=lambda: calls.append("task") or 0,
            supervisor_starter=lambda: calls.append("supervisor") or {"started": True},
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


def _make_runtime(root: Path, *, port: int = 9999) -> None:
    (root / "scripts").mkdir(parents=True)
    (root / "orchestrator").mkdir()
    (root / "data").mkdir()
    (root / "scripts" / "service_supervisor.py").write_text("# ok\n", encoding="utf-8")
    (root / "orchestrator" / "__init__.py").write_text("", encoding="utf-8")
    worker_path = root / "worker-config.json"
    worker_path.write_text(
        json.dumps(
            {
                "endpoint": "http://127.0.0.1:9999",
                "worker_id": "wrong-worker",
            }
        ),
        encoding="utf-8",
    )
    (root / "service-config.json").write_text(
        json.dumps(
            {
                "mode": "worker",
                "install_root": str(root),
                "port": port,
                "ready_url": "http://127.0.0.1:9999/readyz",
                "worker_config": str(worker_path),
                "source_root": str(root),
            }
        ),
        encoding="utf-8",
    )


def test_normalize_runtime_config_repairs_drift_and_preserves_first_backup(tmp_path):
    root = tmp_path / "runtime"
    _make_runtime(root)
    original_service = (root / "service-config.json").read_text(encoding="utf-8")
    original_worker = (root / "worker-config.json").read_text(encoding="utf-8")

    first = module.normalize_runtime_config(root)
    layout = module.validate_runtime_layout(root)

    assert first["normalized"] is True
    assert first["service_backup_created"] is True
    assert first["worker_backup_created"] is True
    assert layout["root"] == root.resolve()

    service = json.loads((root / "service-config.json").read_text(encoding="utf-8"))
    worker = json.loads((root / "worker-config.json").read_text(encoding="utf-8"))
    assert service["mode"] == "control-plane-worker"
    assert service["port"] == 8787
    assert service["ready_url"] == module.CONTROL_PLANE + "/readyz"
    assert worker["endpoint"] == module.CONTROL_PLANE
    assert worker["worker_id"] == "desktop-pdqk954"

    backup_dir = root / "data" / "study-mode-recovery"
    service_backup = backup_dir / "service-config.before-study-recovery.json"
    worker_backup = backup_dir / "worker-config.before-study-recovery.json"
    assert service_backup.read_text(encoding="utf-8") == original_service
    assert worker_backup.read_text(encoding="utf-8") == original_worker

    second = module.normalize_runtime_config(root)
    assert second["service_backup_created"] is False
    assert second["worker_backup_created"] is False
    assert service_backup.read_text(encoding="utf-8") == original_service
    assert worker_backup.read_text(encoding="utf-8") == original_worker


def test_start_validated_supervisor_normalizes_invalid_runtime(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    _make_runtime(root)

    class Process:
        pid = 4321

    observed = {}

    def fake_popen(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return Process()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    result = module.start_validated_supervisor(root)

    assert result["started"] is True
    assert result["runtime_contract_validated"] is True
    assert result["runtime_normalized"] is True
    assert result["normalization"]["normalized"] is True
    assert observed["kwargs"]["cwd"] == str(root.resolve())
    assert "scripts.service_supervisor" in observed["argv"]


def test_recovery_method_reports_normalized_supervisor(tmp_path):
    state = {"supervisor_started": False}

    def ready_probe():
        return state["supervisor_started"]

    def supervisor_starter():
        state["supervisor_started"] = True
        return {
            "started": True,
            "pid_present": True,
            "tracking_marker_removed": True,
            "runtime_contract_validated": True,
            "runtime_normalized": True,
            "normalization": {"normalized": True},
        }

    result = module.recover(
        confirm=module.CONFIRM,
        evidence_path=tmp_path / "evidence.json",
        host=module.EXPECTED_HOST,
        platform="nt",
        timeout_seconds=1,
        ready_probe=ready_probe,
        worker_probe=operational_worker,
        task_runner=lambda: 0,
        supervisor_starter=supervisor_starter,
        sleep_fn=lambda _: None,
    )

    assert result["ok"] is True
    assert result["recovery_method"] == "scheduled_task_then_normalized_supervisor"
    assert result["supervisor_fallback_used"] is True
