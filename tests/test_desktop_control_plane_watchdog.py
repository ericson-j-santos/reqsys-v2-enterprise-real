from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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


def test_start_runner_recovers_without_claiming_github_health(monkeypatch, tmp_path: Path) -> None:
    runner_home = make_runner_home(tmp_path)
    states = iter([
        {"matching_pids": [], "unresolved_pids": [], "observed": []},
        {"matching_pids": [4321], "unresolved_pids": [], "observed": []},
    ])
    monkeypatch.setattr(m, "runner_process_snapshot", lambda runner: next(states))
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
    assert result["listener_pid"] == 4321
    assert result["github_connectivity_verified"] is False
    assert result["pickup_required"] is True
    assert observed["cwd"] == str(runner_home.resolve())
    assert "run.cmd" in " ".join(str(x) for x in observed["args"])


def test_existing_listener_is_process_running_not_healthy(monkeypatch, tmp_path: Path) -> None:
    runner_home = make_runner_home(tmp_path)
    monkeypatch.setattr(
        m,
        "runner_process_snapshot",
        lambda runner: {"matching_pids": [2222], "unresolved_pids": [], "observed": []},
    )
    monkeypatch.setattr(
        m.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not launch")),
    )
    result = m.start_runner(runner_home, tmp_path / "runner.log")
    assert result["status"] == "process_running"
    assert result["listener_pid"] == 2222
    assert result["github_connectivity_verified"] is False
    assert result["pickup_required"] is True


def test_runner_process_snapshot_fails_closed_when_identity_is_unverifiable(
    monkeypatch, tmp_path: Path
) -> None:
    runner_home = make_runner_home(tmp_path)
    monkeypatch.setattr(m, "_runner_process_ids", lambda: [1111])
    monkeypatch.setattr(m, "_process_executable_path", lambda pid: None)
    with pytest.raises(m.WatchdogError, match="identidade"):
        m.runner_process_snapshot(runner_home)


def test_restart_runner_terminates_only_exact_governed_listener(monkeypatch, tmp_path: Path) -> None:
    runner_home = make_runner_home(tmp_path)
    snapshots = iter([
        {"matching_pids": [3333], "unresolved_pids": [], "observed": []},
        {"matching_pids": [], "unresolved_pids": [], "observed": []},
        {"matching_pids": [], "unresolved_pids": [], "observed": []},
    ])
    monkeypatch.setattr(m, "runner_process_snapshot", lambda runner: next(snapshots))
    killed = []
    monkeypatch.setattr(
        m,
        "_taskkill_runner",
        lambda pid: killed.append(pid) or subprocess.CompletedProcess(["taskkill"], 0, "", ""),
    )
    monkeypatch.setattr(
        m,
        "start_runner",
        lambda *args, **kwargs: {
            "status": "recovered",
            "started": True,
            "listener_pid": 4444,
            "github_connectivity_verified": False,
            "pickup_required": True,
        },
    )
    result = m.restart_runner(runner_home, tmp_path / "runner.log")
    assert killed == [3333]
    assert result["previous_listener_pid"] == 3333
    assert result["termination_scope"] == "exact_runner_home"
    assert result["pickup_required"] is True


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


def test_load_installed_metadata_binds_release_and_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(m, "default_runtime_root", lambda: runtime)
    release = runtime / "releases" / ("a" * 40)
    scripts = release / "scripts"
    scripts.mkdir(parents=True)
    release_watchdog = scripts / "desktop_control_plane_watchdog.py"
    release_watchdog.write_text("stub", encoding="utf-8")
    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    launcher = runtime / "run.py"
    launcher.write_text("", encoding="utf-8")
    metadata = runtime / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "runtime_root": str(runtime),
                "release_root": str(release),
                "python_executable": str(python),
                "source_sha": "a" * 40,
                "host": m.EXPECTED_HOST,
            }
        ),
        encoding="utf-8",
    )
    result = m.load_installed_metadata(metadata)
    assert result["release_watchdog"] == release_watchdog.resolve()
    assert result["metadata_path"] == metadata.resolve()


def test_load_installed_metadata_rejects_release_not_bound_to_sha(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    release = runtime / "releases" / "wrong-release"
    scripts = release / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "desktop_control_plane_watchdog.py").write_text("stub", encoding="utf-8")
    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    launcher = runtime / "run.py"
    launcher.write_text("", encoding="utf-8")
    metadata = runtime / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "runtime_root": str(runtime),
                "release_root": str(release),
                "python_executable": str(python),
                "source_sha": "a" * 40,
                "host": m.EXPECTED_HOST,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(m.WatchdogError, match="source_sha"):
        m.load_installed_metadata(metadata)


def test_install_stages_release_when_uac_activation_is_required(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts" / m.RDC_RECOVERY_SCRIPT).write_text("# recovery", encoding="utf-8")
    (source / "scripts" / m.UAC_LAUNCHER_SCRIPT).write_text("# uac", encoding="utf-8")
    runner = make_runner_home(tmp_path)
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(m, "require_windows_desktop", lambda: m.EXPECTED_HOST)
    monkeypatch.setattr(m, "discover_runner_home", lambda explicit=None: runner.resolve())
    monkeypatch.setattr(
        m,
        "register_boot_task",
        lambda **kwargs: (_ for _ in ()).throw(m.WatchdogError("task_scheduler_access_denied")),
    )
    monkeypatch.setattr(
        m,
        "task_status",
        lambda: {"exists": False, "trigger_at_startup": False},
    )
    original_file = m.__file__
    try:
        m.__file__ = str(source / "scripts" / "desktop_control_plane_watchdog.py")
        Path(m.__file__).write_text("# watchdog", encoding="utf-8")
        result = m.install(
            source,
            source_sha="b" * 40,
            python_executable=Path(sys.executable),
            runner_home=runner,
            runtime_root=runtime,
            watch_interval_seconds=30,
            confirm=m.CONFIRM,
        )
    finally:
        m.__file__ = original_file
    assert result["ok"] is True
    assert result["headless_boot_ready"] is False
    assert result["activation_pending"] is True
    assert result["requires_uac_activation"] is True
    assert result["start"]["reason"] == "uac_activation_required"
    assert (runtime / "metadata.json").is_file()
    assert (runtime / "releases" / ("b" * 40) / "scripts" / m.UAC_LAUNCHER_SCRIPT).is_file()


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
    assert "except OSError:\n            pass" not in text
    assert "except Exception:\n        pass" not in text
    assert "reboot" not in text.casefold() or '"reboot_performed": False' in text


def test_runner_config_is_validated_but_never_read() -> None:
    text = MODULE.read_text(encoding="utf-8")
    assert 'RUNNER_REQUIRED = ((".runner",), ("run.cmd",), ("bin", "Runner.Listener.exe"))' in text
    assert 'resolved.joinpath(*parts).is_file()' in text
    assert '.runner").read_' not in text


def test_stop_runner_terminates_only_exact_governed_listener(monkeypatch, tmp_path: Path) -> None:
    runner_home = make_runner_home(tmp_path)
    snapshots = iter([
        {"matching_pids": [7777], "unresolved_pids": [], "observed": []},
        {"matching_pids": [], "unresolved_pids": [], "observed": []},
        {"matching_pids": [], "unresolved_pids": [], "observed": []},
    ])
    monkeypatch.setattr(m, "runner_process_snapshot", lambda runner: next(snapshots))
    killed = []
    monkeypatch.setattr(
        m,
        "_taskkill_runner",
        lambda pid: killed.append(pid) or subprocess.CompletedProcess(["taskkill"], 0, "", ""),
    )
    result = m.stop_runner(runner_home)
    assert killed == [7777]
    assert result["stopped"] is True
    assert result["previous_listener_pid"] == 7777
    assert result["termination_scope"] == "exact_runner_home"
