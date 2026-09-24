import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "noteri_desktop_admin_broker_kick.py"
SPEC = importlib.util.spec_from_file_location("noteri_desktop_admin_broker_kick", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_contract_is_fixed_and_has_no_credentials(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "schtasks.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr(m, "schtasks_executable", lambda: fake)
    seen = {}

    def run(argv):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "SUCCESS", "")

    evidence = tmp_path / "evidence.json"
    result = m.kick(
        confirm=m.CONFIRM,
        evidence_file=evidence,
        run_cmd=run,
        source_host="Noteri",
        platform="nt",
    )
    assert result["ok"] is True
    assert seen["argv"] == [
        str(fake), "/Run", "/S", "DESKTOP-PDQK954", "/TN",
        r"\Automation\ReqSysDesktopAdminBroker",
    ]
    assert "/U" not in seen["argv"]
    assert "/P" not in seen["argv"]
    assert result["task_created_or_modified"] is False
    assert result["credentials_supplied"] is False


def test_failure_is_sanitized_and_fail_closed(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "schtasks.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr(m, "schtasks_executable", lambda: fake)

    def run(argv):
        return subprocess.CompletedProcess(argv, 5, "", "ERRO: Acesso negado.\n")

    result = m.kick(
        confirm=m.CONFIRM,
        evidence_file=tmp_path / "evidence.json",
        run_cmd=run,
        source_host="Noteri",
        platform="nt",
    )
    assert result["ok"] is False
    assert result["result"] == "DESKTOP_ADMIN_BROKER_RUN_BLOCKED"
    assert result["run_returncode"] == 5
    assert "\n" not in result["run_error"]


def test_workflow_is_explicitly_allowlisted() -> None:
    import json

    policy = json.loads(
        (ROOT / ".github" / "self-hosted-runner-policy.json").read_text(encoding="utf-8")
    )
    assert ".github/workflows/noteri-desktop-admin-broker-kick.yml" in policy["approved_workflows"]
    assert "Desktop Admin Broker" in policy["rationale"]


def test_workflow_separates_remote_manual_and_local_probe_routes() -> None:
    raw = (
        ROOT / ".github" / "workflows" / "noteri-desktop-admin-broker-kick.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in raw
    assert "pull_request:" not in raw
    assert "pull_request_target:" not in raw
    assert "\n  push:" in raw
    assert "fix/noteri-desktop-admin-broker-kick-*" in raw

    assert "if: ${{ github.event_name == 'workflow_dispatch' }}" in raw
    assert "if: ${{ github.event_name == 'push' }}" in raw
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "desktop_local_admin_broker_kick.py" in raw
    assert "KICK-LOCAL-DESKTOP-ADMIN-BROKER" in raw
    assert "session_launcher.py" in raw
    assert "command_gateway.py" in raw
    assert "STALL_AFTER_SECONDS: \"60\"" in raw
    assert "secrets." not in raw
