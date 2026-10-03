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
        "self_hosted_dev_maintenance.py",
        "self_hosted_dev_candidate_control.py",
        "reqsys_self_hosted_dev_publish.py",
        "pc24x7_public_dev_tunnel.py",
        "pc24x7_dev_locator_publisher.py",
    }


def test_installer_keeps_scheduled_publication_under_ntfy_anonymous_daily_budget():
    assert installer.SUPERVISOR_INTERVAL_MINUTES == 7
    assert installer.LOCATOR_TTL_MINUTES == 15
    assert installer.MISSED_CYCLE_TOLERANCE == 1
    assert installer.MAX_SCHEDULED_PUBLICATIONS_PER_DAY == 206
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
