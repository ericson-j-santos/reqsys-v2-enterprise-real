from pathlib import Path
import importlib.util

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pc24x7_engineering_orchestrator_recover.py"
spec = importlib.util.spec_from_file_location("recover", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_recovery_is_fixed_to_desktop_dev_and_exact_task():
    assert module.EXPECTED_HOST == "DESKTOP-PDQK954"
    assert module.TASK_NAME == r"\Automation\ReqSysOrchestrator24x7"
    assert module.BASE_URL == "http://127.0.0.1:8787"


def test_registry_evidence_is_sanitized(monkeypatch):
    monkeypatch.setattr(
        module,
        "request_json",
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
                        "eligible": True,
                        "profile": "NORMAL",
                        "capabilities": {"secret": "must-not-leak"},
                    }
                ]
            },
        ),
    )
    result = module.sanitized_registry()
    assert result == {
        "reachable": True,
        "http_status": 200,
        "payload_valid": True,
        "noteri_match_count": 1,
        "noteri": {
            "fresh": True,
            "controller_online": True,
            "auth_valid": True,
            "eligible": True,
            "profile": "NORMAL",
        },
    }


def test_invalid_task_action_fails_closed(monkeypatch):
    monkeypatch.setattr(module.os, "name", "nt")
    monkeypatch.setattr(module.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    monkeypatch.setattr(
        module,
        "task_snapshot",
        lambda: {"exists": True, "enabled": True, "action_valid": False},
    )
    monkeypatch.setattr(
        module,
        "sanitized_registry",
        lambda: {"reachable": False, "http_status": None, "payload_valid": False, "noteri_match_count": None},
    )
    writes = []
    monkeypatch.setattr(module, "atomic_write", lambda path, payload: writes.append(payload))
    assert module.execute(Path("evidence.json"), 30) == 2
    assert writes[-1]["error"] == "scheduled_task_action_invalid"
