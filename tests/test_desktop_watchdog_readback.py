from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/desktop_watchdog_readback.py"
WORKFLOW = ROOT / ".github/workflows/noteri-desktop-watchdog-recovery.yml"
SPEC = importlib.util.spec_from_file_location("desktop_watchdog_readback", SCRIPT)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
SHA = "a" * 40
CID = "desktop-watchdog-readback-123-1"
NOW = datetime(2026, 10, 22, 19, 0, tzinfo=timezone.utc)
XML = """<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
<Triggers><BootTrigger><Enabled>true</Enabled></BootTrigger></Triggers>
<Settings><Enabled>true</Enabled></Settings>
<Principals><Principal><LogonType>S4U</LogonType></Principal></Principals>
</Task>"""


def state():
    return {
        "host": m.EXPECTED_HOST, "service": m.WATCHDOG_SERVICE,
        "source_sha": SHA, "generated_at": NOW.isoformat(), "ok": True,
        "github_runner": {"status": "process_running"},
        "rdc": {"status": "retired_fail_closed", "enabled": False},
    }


def identity(monkeypatch):
    monkeypatch.setattr(m.os, "name", "nt")
    monkeypatch.setattr(m.socket, "gethostname", lambda: m.EXPECTED_HOST)
    monkeypatch.setenv("RUNNER_NAME", m.EXPECTED_HOST)
    monkeypatch.setenv("GITHUB_REPOSITORY", m.EXPECTED_REPOSITORY)
    monkeypatch.setenv("GITHUB_SHA", SHA)


@pytest.mark.parametrize("field,value", [
    ("host", "Noteri"), ("RUNNER_NAME", "other-runner"),
    ("GITHUB_REPOSITORY", "other/repo"), ("GITHUB_SHA", "b" * 40),
])
def test_identity_blocks_before_any_read(monkeypatch, field, value):
    identity(monkeypatch)
    if field == "host":
        monkeypatch.setattr(m.socket, "gethostname", lambda: value)
    else:
        monkeypatch.setenv(field, value)
    monkeypatch.setattr(m, "task_metadata", lambda: pytest.fail("must not read"))
    with pytest.raises(m.ReadbackError):
        m.collect(SHA, CID)


def test_invalid_sha_and_correlation_block(monkeypatch):
    identity(monkeypatch)
    with pytest.raises(m.ReadbackError):
        m.require_identity("not-a-sha", CID)
    with pytest.raises(m.ReadbackError):
        m.require_identity(SHA, "arbitrary-value")


def test_task_xml_separates_enabled_and_boot_trigger():
    assert m.parse_task_xml(XML)["trigger_at_startup"] is True
    disabled = XML.replace("<BootTrigger><Enabled>true", "<BootTrigger><Enabled>false")
    result = m.parse_task_xml(disabled)
    assert result["enabled"] is True
    assert result["trigger_at_startup"] is False
    assert result["logon_type"] == "S4U"
    disabled_task = XML.replace("<Settings><Enabled>true", "<Settings><Enabled>false")
    assert m.parse_task_xml(disabled_task)["enabled"] is False
    assert m.parse_task_xml(XML.replace("S4U", "InteractiveToken"))["logon_type"] == "InteractiveToken"


@pytest.mark.parametrize("raw", ["<broken>", "<Other/>", "<!DOCTYPE Task>" + XML])
def test_invalid_xml_fails_closed(raw):
    with pytest.raises(m.ReadbackError):
        m.parse_task_xml(raw)


@pytest.mark.parametrize("headers", [
    '"TaskName","Last Result"', '"Nome da tarefa","Último resultado"',
])
def test_last_result_pt_en_numeric_not_health(headers):
    result = m.parse_last_result(headers + '\n"' + m.TASK_NAME + '","267009"\n')
    assert result == {"status": "observed", "value": 267009, "successful_cycle_verified": False}


@pytest.mark.parametrize("value", ["unknown", "not-a-number", "9999999999", "private-error"])
def test_last_result_unknown_never_becomes_zero(value):
    result = m.parse_last_result('"TaskName","Last Result"\n"' + m.TASK_NAME + '","' + value + '"\n')
    assert result["status"] == "unavailable"
    assert "value" not in result


def test_wrong_task_csv_is_rejected():
    assert m.parse_last_result('"TaskName","Last Result"\n"Other","0"\n')["status"] == "unavailable"


def test_only_fixed_local_queries_and_no_shell(monkeypatch):
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        text = XML if "/XML" in args else '"TaskName","Last Result"\n"' + m.TASK_NAME + '","0"\n'
        return subprocess.CompletedProcess(args, 0, text, "")
    monkeypatch.setattr(m.subprocess, "run", run)
    result = m.task_metadata()
    assert result["status"] == "observed"
    assert len(calls) == 2
    for args, kwargs in calls:
        assert args[:4] == [r"C:\Windows\System32\schtasks.exe", "/Query", "/TN", m.TASK_NAME]
        assert kwargs["shell"] is False
        assert kwargs["timeout"] == 20
        assert not {"/Run", "/Create", "/Change", "/Delete", "/S"} & set(args)


def test_query_failure_does_not_emit_stderr_or_attempt_repair(monkeypatch):
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "private-error-secret")
    monkeypatch.setattr(m.subprocess, "run", run)
    result = m.task_metadata()
    assert result["exists"] is None
    assert len(calls) == 1
    assert "private-error-secret" not in json.dumps(result)


def service_api(monkeypatch, *, manager=1, service=2, error=0, query=True):
    calls = []
    class Fn:
        def __init__(self, fn):
            self.fn = fn
        def __call__(self, *args):
            return self.fn(*args)
    def open_manager(*args):
        calls.append(("manager", args))
        return manager
    def open_service(*args):
        calls.append(("service", args))
        return service
    def read_status(handle, level, ptr, size, needed):
        ptr._obj.current_state = 4
        ptr._obj.process_id = 123
        return query
    api = SimpleNamespace(
        OpenSCManagerW=Fn(open_manager), OpenServiceW=Fn(open_service),
        QueryServiceStatusEx=Fn(read_status),
        CloseServiceHandle=Fn(lambda handle: calls.append(("close", handle)) or True),
    )
    monkeypatch.setattr(m.ctypes, "WinDLL", lambda *args, **kwargs: api, raising=False)
    monkeypatch.setattr(m.ctypes, "get_last_error", lambda: error, raising=False)
    return calls


def test_service_is_query_only_and_not_connectivity(monkeypatch):
    calls = service_api(monkeypatch)
    result = m.runner_service_metadata()
    assert result["state"] == "running"
    assert result["github_connectivity_verified"] is False
    assert ("manager", (None, None, 1)) in calls
    assert ("service", (1, m.EXPECTED_RUNNER_SERVICE, 4)) in calls
    assert ("close", 1) in calls and ("close", 2) in calls


def test_exact_service_absence_not_all_services(monkeypatch):
    service_api(monkeypatch, service=0, error=1060)
    result = m.runner_service_metadata()
    assert result == {"status": "observed", "exists": False, "other_services_checked": False}


@pytest.mark.parametrize("options", [{"manager": 0}, {"service": 0, "error": 5}, {"query": False}])
def test_service_failure_is_not_absence(monkeypatch, options):
    service_api(monkeypatch, **options)
    result = m.runner_service_metadata()
    assert result["status"] == "unavailable"
    assert "exists" not in result


def test_state_allowlist_discards_errors_paths_and_unknown_fields():
    payload = state()
    payload.update(error="private-secret", message="private-secret", path="private-secret")
    payload["github_runner"].update(error="private-secret", path="private-secret")
    payload["ok"] = "private-secret"
    result = m.sanitize_state(payload, NOW)
    assert "private-secret" not in json.dumps(result)
    assert result["last_cycle_ok"] is None
    assert result["installed_release_verified"] is False
    assert result["continuous_cycles_verified"] is False
    assert result["reqsys_producer_verified"] is False
    assert result["last_cycle_source_sha"] == SHA


@pytest.mark.parametrize("key,value", [
    ("host", "Other"), ("service", "other-service"), ("source_sha", "private-secret"),
    ("generated_at", "bad-time"), ("generated_at", "2026-10-23T19:00:00+00:00"),
    ("generated_at", "2026-10-22T19:00:00"),
])
def test_state_identity_and_timestamp_fail_closed(key, value):
    payload = state()
    payload[key] = value
    result = m.sanitize_state(payload, NOW)
    assert result["status"] == "unavailable"
    assert "private-secret" not in json.dumps(result)


def test_stale_state_not_continuous_execution():
    payload = state()
    payload["generated_at"] = "2026-10-22T18:00:00+00:00"
    result = m.sanitize_state(payload, NOW)
    assert result["fresh_within_120_seconds"] is False
    assert result["continuous_cycles_verified"] is False


def test_state_file_is_bounded_and_json_only(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state()), encoding="utf-8")
    assert m._read_state(path)["source_sha"] == SHA
    path.write_bytes(b"x" * (m.MAX_STATE_BYTES + 1))
    with pytest.raises(m.ReadbackError):
        m._read_state(path)
    path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError):
        m._read_state(path)


def test_reparse_ancestor_is_rejected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "state.json").write_text(json.dumps(state()), encoding="utf-8")
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink unavailable in this test environment")
    with pytest.raises(m.ReadbackError, match="reparse"):
        m._read_state(link / "state.json")


def test_missing_state_is_explicit_without_config_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_fixed_runtime_root", lambda: tmp_path)
    result = m.watchdog_state_metadata(NOW)
    assert result == {"status": "unavailable", "reason": "state_missing"}
    assert not list(tmp_path.iterdir())


def test_partial_collection_does_not_assert_health_or_producer(monkeypatch):
    monkeypatch.setattr(m, "require_identity", lambda *args: None)
    monkeypatch.setattr(m, "task_metadata", lambda: {"status": "unavailable"})
    monkeypatch.setattr(m, "runner_service_metadata", lambda: {"status": "unavailable"})
    monkeypatch.setattr(m, "watchdog_state_metadata", lambda observed: {"status": "unavailable"})
    result = m.collect(SHA, CID)
    assert result["probe_ok"] is True
    assert result["collection_complete"] is False
    assert result["result"] == "DESKTOP_WATCHDOG_READBACK_PARTIAL"
    assert result["runtime_ready"] is False
    assert result["reqsys_producer_verified"] is False
    assert result["task_action_identity_verified"] is False
    assert result["runner_service_identity_verified"] is False
    for field in ("secrets_read", "private_config_read", "task_created_or_modified",
                  "task_run_requested", "service_mutated", "production_touched"):
        assert result[field] is False


def test_workflow_readback_is_manual_bounded_and_separate():
    raw = WORKFLOW.read_text(encoding="utf-8")
    lane = raw.split("  watchdog-readback:", 1)[1]
    assert "inputs.mode == 'watchdog-readback'" in lane
    assert "github.event_name == 'workflow_dispatch'" in lane
    assert "default: watchdog" in raw
    assert "desktop_watchdog_readback.py" in lane
    assert "session_launcher.py" in lane and "command_gateway.py" in lane
    assert "--require-runner-version-preflight" in lane
    assert "RULES_SHA: fabaccc32abbbf6f95be443629ef2ebb1246dad5" in lane
    assert "SESSION_LAUNCH_OK" in lane and "state_validated" in lane
    assert '"--expected-head", $env:ANCHOR_SHA' in lane
    assert "persist-credentials: false" in lane
    assert "secrets." not in lane
    assert "--runtime-root" not in lane
    assert "RUN-EXISTING" not in lane
    assert "/Run" not in lane and "Start-Service" not in lane
    assert "Materialize verified persistent watchdog Python" not in lane
    assert "runtime_ready" in lane and "reqsys_producer_verified" in lane
    assert "noteri_desktop_watchdog_rpc_recovery.py" not in lane
