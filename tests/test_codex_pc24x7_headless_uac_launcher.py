from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE = SCRIPTS / "codex_pc24x7_headless_uac_launcher.py"
SPEC = importlib.util.spec_from_file_location("codex_pc24x7_headless_uac_launcher", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_launcher_preconditions_are_fail_closed() -> None:
    m.validate_launcher(
        host="DESKTOP-PDQK954",
        platform="nt",
        confirm=m.LAUNCH_CONFIRM,
    )
    with pytest.raises(RuntimeError, match="host"):
        m.validate_launcher(host="Noteri", platform="nt", confirm=m.LAUNCH_CONFIRM)
    with pytest.raises(RuntimeError, match="Windows"):
        m.validate_launcher(host="DESKTOP-PDQK954", platform="posix", confirm=m.LAUNCH_CONFIRM)
    with pytest.raises(RuntimeError, match="confirmação"):
        m.validate_launcher(host="DESKTOP-PDQK954", platform="nt", confirm="NO")


def test_task_headless_ready_requires_boot_and_s4u() -> None:
    assert m.task_headless_ready(
        {"exists": True, "trigger_at_startup": True, "logon_type": "S4U"}
    )
    assert not m.task_headless_ready(
        {"exists": True, "trigger_at_startup": False, "logon_type": "S4U"}
    )
    assert not m.task_headless_ready(
        {"exists": True, "trigger_at_startup": True, "logon_type": "InteractiveToken"}
    )


def test_load_installation_is_bound_to_runtime_release(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    release = runtime / "releases" / ("a" * 40)
    script = release / "scripts" / "codex_pc24x7_supervisor.py"
    script.parent.mkdir(parents=True)
    script.write_text("x", encoding="utf-8")
    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    launcher = runtime / "run.py"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text("x", encoding="utf-8")
    metadata = runtime / "metadata.json"
    metadata.write_text(
        '{"runtime_root":"' + str(runtime).replace("\\", "\\\\") +
        '","release_root":"' + str(release).replace("\\", "\\\\") +
        '","python_executable":"' + str(python).replace("\\", "\\\\") +
        '","source_sha":"' + ("a" * 40) + '"}',
        encoding="utf-8",
    )

    result = m.load_installation(metadata)

    assert result["release_supervisor"] == script.resolve()
    assert result["launcher"] == launcher.resolve()


def test_elevated_command_is_exact_and_contains_no_secret_options(tmp_path: Path) -> None:
    installation = {
        "release_supervisor": tmp_path / "codex_pc24x7_supervisor.py",
        "python_executable": tmp_path / "python.exe",
        "launcher": tmp_path / "run.py",
    }
    args = m.build_elevated_arguments(installation)
    parsed = subprocess.list2cmdline(
        [
            str(installation["release_supervisor"]),
            "register-task-com",
            "--python-executable",
            str(installation["python_executable"]),
            "--launcher",
            str(installation["launcher"]),
        ]
    )
    assert args == parsed
    assert "register-task-com" in args
    assert "password" not in args.casefold()
    assert "token" not in args.casefold()


def test_finalize_removes_logon_fallback_only_after_verified_task(monkeypatch, tmp_path: Path) -> None:
    metadata_path = tmp_path / "metadata.json"
    installation = {
        "metadata": {"persistence_mode": "hkcu_run_at_logon", "requires_user_logon": True},
        "metadata_path": metadata_path,
    }
    written = {}
    removed = {"value": False}
    monkeypatch.setattr(
        m.supervisor,
        "task_status",
        lambda: {"exists": True, "trigger_at_startup": True, "logon_type": "S4U"},
    )
    monkeypatch.setattr(m.supervisor, "now_iso", lambda: "2026-09-19T22:30:00+00:00")
    monkeypatch.setattr(
        m.supervisor,
        "atomic_json",
        lambda path, payload: written.update({"path": path, "payload": payload}),
    )
    monkeypatch.setattr(
        m.supervisor,
        "_remove_run_key",
        lambda: removed.update({"value": True}),
    )
    monkeypatch.setattr(m.supervisor, "run_key_status", lambda: {"configured": False})

    result = m.finalize_headless(installation)

    assert result["metadata"]["persistence_mode"] == "task_at_startup_no_password"
    assert result["metadata"]["requires_user_logon"] is False
    assert result["metadata"]["headless_24x7"] is True
    assert written["path"] == metadata_path
    assert removed["value"] is True
