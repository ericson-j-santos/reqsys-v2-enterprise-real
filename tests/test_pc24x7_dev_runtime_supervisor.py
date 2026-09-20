import importlib.util
from pathlib import Path

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
        "pc24x7_public_dev_tunnel.py",
        "pc24x7_tailscale_funnel.py",
    }
