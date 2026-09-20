from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "desktop_control_plane_watchdog.py"
SPEC = importlib.util.spec_from_file_location("desktop_control_plane_watchdog", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def make_runner_home(tmp_path: Path) -> Path:
    root = tmp_path / "actions-runner"
    (root / "bin").mkdir(parents=True)
    (root / ".runner").write_text("opaque-config", encoding="utf-8")
    (root / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (root / "bin" / "Runner.Listener.exe").write_bytes(b"stub")
    return root


def test_rejects_other_host(monkeypatch) -> None:
    monkeypatch.setattr(m.os, "name", "nt")
    monkeypatch.setattr(m.socket, "gethostname", lambda: "Noteri")
    with pytest.raises(m.WatchdogError, match="host não autorizado"):
        m.require_windows_desktop()


def test_runner_home_requires_local_runner_contract(tmp_path: Path) -> None:
    root = tmp_path / "actions-runner"
    root.mkdir()
    with pytest.raises(m.WatchdogError, match="arquivos ausentes"):
        m.validate_runner_home(root)

    valid = make_runner_home(tmp_path)
    assert m.validate_runner_home(valid) == valid.resolve()


def test_discovery_prefers_explicit_runner_home(tmp_path: Path) -> None:
    valid = make_runner_home(tmp_path)
    assert m.discover_runner_home(valid) == valid.resolve()


def test_rdc_claim_missing_is_not_healthy(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(m, "RDC_HEADLESS_CLAIM", tmp_path / "missing.json")
    assert m.read_rdc_claim() == {"fresh": False, "reason": "claim_missing"}


def test_rdc_claim_fresh_is_accepted(monkeypatch, tmp_path: Path) -> None:
    from datetime import datetime, timezone

    claim = tmp_path / "claim.json"
    claim.write_text(
        json.dumps({"ready": True, "updated_at": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "RDC_HEADLESS_CLAIM", claim)
    result = m.read_rdc_claim()
    assert result["fresh"] is True
    assert result["reason"] == "fresh"


def test_recover_rdc_skips_restart_when_claim_is_fresh(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(m, "read_rdc_claim", lambda: {"fresh": True, "reason": "fresh"})
    result = m.recover_rdc(
        python_executable=Path("python"),
        recovery_script=tmp_path / "recovery.py",
        evidence_path=tmp_path / "evidence.json",
    )
    assert result["status"] == "healthy"
    assert result["recovered"] is False


def test_recover_rdc_uses_governed_local_script(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(m, "read_rdc_claim", lambda: {"fresh": False, "reason": "stale"})
    evidence = tmp_path / "evidence.json"

    def fake_run(args, **kwargs):
        assert m.RDC_RECOVERY_CONFIRM in args
        evidence.write_text(
            json.dumps(
                {
                    "ok": True,
                    "mode": "headless_transport_proven_with_interactive_standby",
                    "owner": "headless",
                    "fallback_armed": True,
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    result = m.recover_rdc(
        python_executable=Path("python"),
        recovery_script=tmp_path / "recovery.py",
        evidence_path=evidence,
    )
    assert result["status"] == "recovered"
    assert result["fallback_armed"] is True


def test_start_runner_recovers_without_github_api(monkeypatch, tmp_path: Path) -> None:
    runner_home = make_runner_home(tmp_path)
    states = iter([False, True])
    monkeypatch.setattr(m, "runner_running", lambda: next(states))
    monkeypatch.setattr(m, "_creationflags", lambda: 0)

    class FakeProcess:
        pid = 1234
        returncode = None

        def poll(self):
            return None

    observed = {}

    def fake_popen(args, **kwargs):
        observed["args"] = args
        observed["cwd"] = kwargs["cwd"]
        return FakeProcess()

    monkeypatch.setattr(m.subprocess, "Popen", fake_popen)
    result = m.start_runner(runner_home, tmp_path / "runner.log")
    assert result["status"] == "recovered"
    assert result["launcher_pid"] == 1234
    assert observed["cwd"] == str(runner_home.resolve())
    assert "run.cmd" in " ".join(str(x) for x in observed["args"])


def test_cycle_recovers_rdc_and_runner_and_writes_sanitized_state(monkeypatch, tmp_path: Path) -> None:
    runner_home = make_runner_home(tmp_path)
    release = tmp_path / "release"
    scripts = release / "scripts"
    scripts.mkdir(parents=True)
    (scripts / m.RDC_RECOVERY_SCRIPT).write_text("# stub\n", encoding="utf-8")
    runtime = tmp_path / "runtime"

    monkeypatch.setattr(m, "require_windows_desktop", lambda: m.EXPECTED_HOST)
    monkeypatch.setattr(m, "validate_runner_home", lambda path: runner_home)
    monkeypatch.setattr(
        m,
        "recover_rdc",
        lambda **kwargs: {"status": "recovered", "recovered": True, "fallback_armed": True},
    )
    monkeypatch.setattr(
        m,
        "start_runner",
        lambda *args, **kwargs: {"status": "recovered", "started": True},
    )

    metadata = {
        "runtime_root": str(runtime),
        "release_root": str(release),
        "runner_home": str(runner_home),
        "python_executable": "python",
        "source_sha": "a" * 40,
    }
    payload = m.cycle(metadata)
    assert payload["ok"] is True
    assert payload["rdc"]["status"] == "recovered"
    assert payload["github_runner"]["status"] == "recovered"
    assert payload["production_touched"] is False
    assert payload["secrets_read"] is False
    persisted = json.loads((runtime / "state.json").read_text(encoding="utf-8"))
    assert persisted["ok"] is True


def test_install_requires_exact_confirmation(tmp_path: Path) -> None:
    with pytest.raises(m.WatchdogError, match="confirmação inválida"):
        m.install(
            tmp_path,
            source_sha="a" * 40,
            python_executable=Path("python"),
            runner_home=None,
            runtime_root=tmp_path / "runtime",
            watch_interval_seconds=30,
            confirm="NO",
        )


def test_source_contract_is_independent_of_rdc_and_github_runner(tmp_path: Path) -> None:
    text = MODULE.read_text(encoding="utf-8")
    assert 'TASK_LEAF = "ReqSysDesktopControlPlaneWatchdog"' in text
    assert 'TASK_TRIGGER_BOOT = 8' in text
    assert 'TASK_LOGON_S4U = 2' in text
    assert 'definition.Settings.RestartCount = 999' in text
    assert "pc24x7_rdc_recovery.py" in text
    assert "Runner.Listener.exe" in text
    assert "run.cmd" in text
    assert "github.com" not in text.casefold()
    assert "api.github" not in text.casefold()
    assert "workflow_dispatch" not in text
    assert "reboot" not in text.casefold() or '"reboot_performed": False' in text


def test_runner_config_is_validated_but_never_read() -> None:
    text = MODULE.read_text(encoding="utf-8")
    assert 'RUNNER_REQUIRED = ((".runner",), ("run.cmd",), ("bin", "Runner.Listener.exe"))' in text
    assert 'resolved.joinpath(*parts).is_file()' in text
    assert '.runner").read_' not in text
