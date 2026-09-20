from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE = SCRIPTS / "desktop_control_plane_watchdog_uac_launcher.py"
SPEC = importlib.util.spec_from_file_location(
    "desktop_control_plane_watchdog_uac_launcher", MODULE
)
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
        m.validate_launcher(
            host="DESKTOP-PDQK954",
            platform="posix",
            confirm=m.LAUNCH_CONFIRM,
        )
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
        {
            "exists": True,
            "trigger_at_startup": True,
            "logon_type": "InteractiveToken",
        }
    )


def test_elevated_command_is_exact_metadata_only(tmp_path: Path) -> None:
    installation = {
        "release_watchdog": tmp_path / "desktop_control_plane_watchdog.py",
        "metadata_path": tmp_path / "metadata.json",
    }
    args = m.build_elevated_arguments(installation)
    expected = subprocess.list2cmdline(
        [
            str(installation["release_watchdog"]),
            "register-task-com",
            "--metadata",
            str(installation["metadata_path"]),
        ]
    )
    assert args == expected
    assert "register-task-com" in args
    assert "--metadata" in args
    assert "--launcher" not in args
    assert "--python-executable" not in args
    assert "password" not in args.casefold()
    assert "token" not in args.casefold()


def test_finalize_requires_verified_task_before_start(
    monkeypatch, tmp_path: Path
) -> None:
    metadata_path = tmp_path / "metadata.json"
    installation = {
        "metadata": {
            "activation_pending": True,
            "requires_uac_activation": True,
        },
        "metadata_path": metadata_path,
    }
    started = {"value": False}
    written = {}
    monkeypatch.setattr(
        m.watchdog,
        "task_status",
        lambda: {
            "exists": True,
            "trigger_at_startup": True,
            "logon_type": "S4U",
        },
    )
    monkeypatch.setattr(
        m.watchdog,
        "now_iso",
        lambda: "2026-09-20T19:00:00+00:00",
    )
    monkeypatch.setattr(
        m.watchdog,
        "atomic_json",
        lambda path, payload: written.update({"path": path, "payload": payload}),
    )
    monkeypatch.setattr(
        m.watchdog,
        "run_watchdog_task",
        lambda: started.update({"value": True}) or {"run_returncode": 0},
    )
    result = m.finalize_activation(installation)
    assert result["metadata"]["headless_boot_ready"] is True
    assert result["metadata"]["activation_pending"] is False
    assert result["metadata"]["requires_uac_activation"] is False
    assert written["path"] == metadata_path
    assert started["value"] is True


def test_finalize_fails_closed_without_s4u(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        m.watchdog,
        "task_status",
        lambda: {
            "exists": True,
            "trigger_at_startup": True,
            "logon_type": "InteractiveToken",
        },
    )
    with pytest.raises(RuntimeError, match="AtStartup S4U"):
        m.finalize_activation(
            {"metadata": {}, "metadata_path": tmp_path / "metadata.json"}
        )
