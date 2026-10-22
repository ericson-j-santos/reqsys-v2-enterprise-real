import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


supervisor = load("pc24x7_dev_runtime_supervisor", "scripts/pc24x7_dev_runtime_supervisor.py")
installer = load("pc24x7_dev_runtime_supervisor_install", "scripts/pc24x7_dev_runtime_supervisor_install.py")


def test_supervisor_targets_only_dev_gateway():
    assert supervisor.LOCAL_GATEWAY == "http://127.0.0.1:8083"
    assert "prod" not in supervisor.LOCAL_GATEWAY.lower()
    assert "stg" not in supervisor.LOCAL_GATEWAY.lower()


def test_supervisor_knows_only_live_dev_containers():
    assert supervisor.CONTAINERS == (
        "reqsys-live-api-1",
        "reqsys-live-frontend-1",
        "reqsys-live-nginx-1",
    )


def test_installer_uses_user_level_recurring_task_and_persistent_copy():
    assert installer.TASK_NAME == "ReqSys-Dev-Runtime-Supervisor"
    assert installer.PERSISTENT_SUPERVISOR.name == "pc24x7_dev_runtime_supervisor.py"
    assert "RuntimeSupervisor" in str(installer.PERSISTENT_SUPERVISOR)
    assert set(installer.SOURCE_SCRIPTS) == {
        "pc24x7_dev_runtime_supervisor.py",
        "self_hosted_dev_maintenance.py",
        "self_hosted_dev_candidate_control.py",
        "reqsys_self_hosted_dev_publish.py",
        "pc24x7_public_dev_tunnel.py",
        "pc24x7_dev_locator_publisher.py",
    }
    assert installer.RUNTIME_PYTHON.name == "python.exe"
    assert "RuntimeSupervisor" in str(installer.RUNTIME_PYTHON)
    assert installer.RUNTIME_PYTHON_PACKAGES == (
        "cryptography==50.0.0",
        "pywin32==312",
    )


def test_installer_wrapper_uses_dedicated_runtime_python(monkeypatch, tmp_path):
    monkeypatch.setattr(installer, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(installer, "WRAPPER", tmp_path / "logs" / "run.cmd")
    monkeypatch.setattr(installer, "PERSISTENT_SUPERVISOR", tmp_path / "supervisor.py")
    monkeypatch.setattr(installer, "RUNTIME_DIR", tmp_path / "runtime")
    runtime_python = tmp_path / "runtime-python" / "python.exe"

    installer.write_wrapper(runtime_python)

    wrapper = installer.WRAPPER.read_text(encoding="utf-8")
    assert str(runtime_python) in wrapper
    assert f'cd /d "{installer.RUNTIME_DIR}"' in wrapper
    assert "-m scripts.pc24x7_dev_runtime_supervisor --apply" in wrapper
    assert str(installer.PERSISTENT_SUPERVISOR) not in wrapper
    assert str(Path(installer.sys.executable)) not in wrapper


def test_task_hardening_uses_dedicated_runtime_python(monkeypatch, tmp_path):
    calls = []
    expected = {
        "DisallowStartIfOnBatteries": False,
        "StopIfGoingOnBatteries": False,
        "StartWhenAvailable": True,
        "ExecutionTimeLimit": "PT10M",
        "LogonType": 3,
        "InteractiveSessionRequired": True,
    }

    def fake_run(args):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=json.dumps(expected), stderr="")

    monkeypatch.setattr(installer.os, "name", "nt")
    monkeypatch.setattr(installer, "run", fake_run)
    runtime_python = tmp_path / "runtime-python" / "python.exe"

    assert installer.harden_task_settings(runtime_python) == expected
    assert calls[0][0] == str(runtime_python)
    assert "import win32com.client" in calls[0][2]
    assert "registered.Definition.Principal.LogonType" in calls[0][2]
    assert calls[0][-1] == installer.TASK_NAME


def test_installer_keeps_scheduled_publication_under_ntfy_anonymous_daily_budget():
    assert installer.SUPERVISOR_INTERVAL_MINUTES == 6
    assert installer.LOCATOR_TTL_MINUTES == 15
    assert installer.MISSED_CYCLE_TOLERANCE == 1
    assert installer.MAX_SCHEDULED_PUBLICATIONS_PER_DAY == 240
    assert installer.NTFY_ANONYMOUS_DAILY_MESSAGE_LIMIT == 250
    assert (
        installer.MAX_SCHEDULED_PUBLICATIONS_PER_DAY
        < installer.NTFY_ANONYMOUS_DAILY_MESSAGE_LIMIT
    )

    raw = (ROOT / "scripts" / "pc24x7_dev_runtime_supervisor_install.py").read_text(
        encoding="utf-8"
    )
    assert '"/MO", str(SUPERVISOR_INTERVAL_MINUTES)' in raw


def test_installer_cadence_tolerates_one_missed_cycle_before_locator_expiry():
    renewal_after_one_missed_cycle = (
        installer.SUPERVISOR_INTERVAL_MINUTES
        * (installer.MISSED_CYCLE_TOLERANCE + 1)
    )
    assert renewal_after_one_missed_cycle < installer.LOCATOR_TTL_MINUTES
    assert installer.LOCATOR_TTL_MINUTES - renewal_after_one_missed_cycle >= 3


def test_supervisor_has_no_tailscale_or_nport_critical_dependency():
    assert supervisor.PUBLIC_TUNNEL.name == "pc24x7_public_dev_tunnel.py"
    assert supervisor.LOCATOR_PUBLISHER.name == "pc24x7_dev_locator_publisher.py"
    raw = (ROOT / "scripts" / "pc24x7_dev_runtime_supervisor.py").read_text(encoding="utf-8").lower()
    assert "tailscale_funnel" not in raw
    assert "pc24x7_nport_tunnel.py" not in raw


def test_supervisor_requires_runtime_health_and_build_info_before_publication():
    raw = (ROOT / "scripts" / "pc24x7_dev_runtime_supervisor.py").read_text(encoding="utf-8")
    assert '"/api/runtime/health"' in raw
    assert '"/api/runtime/build-info"' in raw
    assert '"local_runtime_contract_failed"' in raw
    assert '"/api/runtime/readiness"' in raw
    assert '"/@vite/client"' in raw
    assert 'for key in ("frontend", "health", "runtime_health", "runtime_readiness", "build_info")' in raw
    assert 'payload["local_after"]["vite_client"].get("status") == 404' in raw
    assert 'locator_ready if args.apply else True' in raw


def _run_installer_case(monkeypatch, capsys, *, create_rc=0, trigger_rc=0, logon_type=3):
    """Simula apenas o Schtasks; nunca toca a tarefa real ou a identidade DPAPI."""
    calls = []
    monkeypatch.setattr(installer, "materialize_runtime", lambda: {})
    monkeypatch.setattr(installer, "ensure_runtime_python", lambda: Path("C:/runtime/python.exe"))
    monkeypatch.setattr(installer, "write_wrapper", lambda _: None)
    monkeypatch.setattr(
        installer,
        "harden_task_settings",
        lambda _: {"LogonType": logon_type, "InteractiveSessionRequired": logon_type == 3},
    )

    def fake_run(args):
        calls.append(args)
        assert args[0] == "schtasks"
        if "/Create" in args:
            code = create_rc
        elif "/Run" in args:
            code = trigger_rc
        else:
            raise AssertionError("unexpected schtasks command")
        return SimpleNamespace(returncode=code, stdout="", stderr="")

    monkeypatch.setattr(installer, "run", fake_run)
    exit_code = installer.install()
    output = capsys.readouterr()
    payload = json.loads(output.out) if output.out.strip() else None
    return exit_code, payload, output.err, calls


def test_installer_trigger_failure_must_not_be_reported_as_success(monkeypatch, capsys):
    code, payload, _, calls = _run_installer_case(
        monkeypatch, capsys, trigger_rc=5,
    )
    assert code == 2
    assert payload["status"] == "trigger_failed"
    assert payload["trigger_returncode"] == 5
    assert payload["trigger_accepted"] is False
    assert payload["task_registered"] is True
    assert payload["runtime_verified"] is False
    assert len(calls) == 2
    # Controle negativo: implementação antiga retornava 0 e status=installed.
    assert payload["status"] != "installed"


def test_installer_accepted_trigger_is_registration_only(monkeypatch, capsys):
    code, payload, _, calls = _run_installer_case(monkeypatch, capsys)
    assert code == 0
    assert payload["status"] == "registered_pending_runtime_verification"
    assert payload["trigger_accepted"] is True
    assert payload["runtime_verified"] is False
    assert payload["independent_of_user_logon"] is False
    assert payload["requires_interactive_session"] is True
    assert len(calls) == 2


def test_installer_mismatched_logon_mode_fails_before_trigger(monkeypatch, capsys):
    code, payload, stderr, calls = _run_installer_case(
        monkeypatch, capsys, logon_type=2,
    )
    assert code == 2
    assert payload is None
    assert "task_logon_mode_readback_mismatch" in stderr
    assert len(calls) == 1
    assert "/Run" not in calls[0]


def test_installer_create_failure_prevents_start_and_success(monkeypatch, capsys):
    code, payload, _, calls = _run_installer_case(
        monkeypatch, capsys, create_rc=7,
    )
    assert code == 2
    assert payload is None
    assert len(calls) == 1
    assert "/Create" in calls[0]


def test_installer_decision_replay_does_not_create_new_effect(monkeypatch, capsys):
    first = _run_installer_case(monkeypatch, capsys, trigger_rc=5)
    second = _run_installer_case(monkeypatch, capsys, trigger_rc=5)
    assert first[:3] == second[:3]
    assert first[3] == second[3]
    assert all(call[0] == "schtasks" for call in first[3])
