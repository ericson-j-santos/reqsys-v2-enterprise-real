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
