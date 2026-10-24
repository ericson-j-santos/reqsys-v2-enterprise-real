"""Regressão de controle do preflight do reparador do Desktop."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "desktop_admin_broker_recovery_preflight.py"
SPEC = importlib.util.spec_from_file_location("desktop_broker_probe", SCRIPT)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

SHA = "a" * 40


def stage(base: Path, *, tamper: bool = False) -> None:
    for _, leaf, _ in probe.TASKS.values():
        root = base / "ReqSys" / leaf
        release = root / "releases" / SHA
        release.mkdir(parents=True)
        (root / "run.py").write_text("# staged launcher", encoding="utf-8")
        python = root / "python.exe"
        python.write_bytes(b"staged-binary-placeholder")
        metadata = {
            "host": probe.HOST, "source_sha": SHA,
            "runtime_root": str(root), "release_root": str(release),
            "python_executable": str(python),
        }
        if tamper and leaf == "DesktopAdminBroker":
            metadata["release_root"] = str(base / "outside" / SHA)
        (root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


def task_xml(base: Path, leaf: str, runlevel: str, *, logon: str = "S4U") -> str:
    root = base / "ReqSys" / leaf
    return f"""<?xml version="1.0"?>
<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><BootTrigger><Enabled>true</Enabled></BootTrigger></Triggers>
  <Principals><Principal><LogonType>{logon}</LogonType><RunLevel>{runlevel}</RunLevel></Principal></Principals>
  <Actions><Exec><Command>{root / 'python.exe'}</Command><Arguments>"{root / 'run.py'}"</Arguments><WorkingDirectory>{root}</WorkingDirectory></Exec></Actions>
</Task>"""


def run_probe(base: Path, *, elevated: bool, auth: bool = True,
              missing: str | None = None, bad_s4u: bool = False) -> dict:
    task_data = {}
    for key, (name, leaf, runlevel) in probe.TASKS.items():
        task_data[name] = None if key == missing else task_xml(
            base, leaf, runlevel, logon=("Password" if bad_s4u and key == "broker" else "S4U")
        )
    return probe.inspect(
        base=base, host="DESKTOP-PDQK954", platform="nt",
        elevated=elevated, gh_authenticated=auth,
        query_xml=task_data.get,
    )


def test_healthy_existing_tasks_and_gh_auth(tmp_path: Path) -> None:
    stage(tmp_path)
    result = run_probe(tmp_path, elevated=False)
    assert result["status"] == "EXISTING_TASKS_AND_AUTH_READY"
    assert result["preflight_completed"] is True
    assert result["task_contract"] == {"broker": True, "watchdog": True}
    assert result["task_created_or_modified"] is False
    assert result["repaired"] is False


def test_missing_broker_task_eligible_only_if_elevated(tmp_path: Path) -> None:
    stage(tmp_path)
    ready = run_probe(tmp_path, elevated=True, missing="broker")
    blocked = run_probe(tmp_path, elevated=False, missing="broker")
    assert ready["status"] == "NATIVE_REPAIR_ELIGIBLE_NOT_EXECUTED"
    assert blocked["status"] == "BLOCKED_ADMIN_ELEVATION_REQUIRED"
    assert ready["task_contract"]["broker"] is False


def test_invalid_persistent_metadata_fails_closed(tmp_path: Path) -> None:
    stage(tmp_path, tamper=True)
    result = run_probe(tmp_path, elevated=True)
    assert result["status"] == "BLOCKED_PERSISTENT_RUNTIME_INVALID"
    assert result["runtime_contract"]["broker"] is False


def test_logon_type_drift_blocks_readiness(tmp_path: Path) -> None:
    stage(tmp_path)
    result = run_probe(tmp_path, elevated=False, bad_s4u=True)
    assert result["status"] == "BLOCKED_ADMIN_ELEVATION_REQUIRED"
    assert result["task_contract"]["broker"] is False


def test_local_gh_auth_is_separate_precondition(tmp_path: Path) -> None:
    stage(tmp_path)
    result = run_probe(tmp_path, elevated=True, auth=False)
    assert result["status"] == "BLOCKED_GH_LOCAL_AUTH_UNAVAILABLE"


def test_foreign_host_is_rejected_before_task_query(tmp_path: Path) -> None:
    def never_called(_: str) -> str | None:
        pytest.fail("Task Scheduler must not be queried on a foreign host")
    result = probe.inspect(
        base=tmp_path, host="Noteri", platform="nt",
        elevated=True, gh_authenticated=True, query_xml=never_called,
    )
    assert result["status"] == "BLOCKED_WRONG_HOST_OR_PLATFORM"
    assert result["preflight_completed"] is False


def test_probe_cannot_modify_tasks_or_expose_secrets() -> None:
    raw = SCRIPT.read_text(encoding="utf-8").casefold()
    assert '"/query"' in raw
    for dangerous in (
        '"/run"', '"/create"', '"/change"', "registertaskdefinition",
        "start-process", "invoke-restmethod", "invoke-webrequest", "read-host",
    ):
        assert dangerous not in raw
    assert "capture_output=true" in raw
    assert "secrets_logged" in raw


def test_workflow_gate_is_owner_only_and_read_only() -> None:
    workflow = (ROOT / ".github/workflows/desktop-admin-broker-recovery-preflight.yml").read_text(encoding="utf-8")
    gateway = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text(encoding="utf-8")
    policy = json.loads((ROOT / ".github/self-hosted-runner-policy.json").read_text(encoding="utf-8"))
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in workflow
    assert "session_launcher.py" in workflow
    assert "command_gateway.py" in workflow
    assert '"--risk", "1"' in workflow
    assert "NATIVE_REPAIR_ELIGIBLE_NOT_EXECUTED" in SCRIPT.read_text(encoding="utf-8")
    assert "/reqsys run desktop-admin-broker-recovery-preflight" in gateway
    assert "desktop-admin-broker-recovery-preflight.yml" in gateway
    assert ".github/workflows/desktop-admin-broker-recovery-preflight.yml" in policy["approved_workflows"]
