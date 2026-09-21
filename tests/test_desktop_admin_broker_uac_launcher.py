from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE = SCRIPTS / "desktop_admin_broker_uac_launcher.py"
SPEC = importlib.util.spec_from_file_location("desktop_admin_broker_uac_launcher", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_launcher_preconditions_fail_closed() -> None:
    m.validate_launcher(
        host=m.broker.EXPECTED_HOST,
        platform="nt",
        confirm=m.LAUNCH_CONFIRM,
    )
    with pytest.raises(RuntimeError, match="host"):
        m.validate_launcher(host="Noteri", platform="nt", confirm=m.LAUNCH_CONFIRM)
    with pytest.raises(RuntimeError, match="Windows"):
        m.validate_launcher(host=m.broker.EXPECTED_HOST, platform="posix", confirm=m.LAUNCH_CONFIRM)
    with pytest.raises(RuntimeError, match="confirmação"):
        m.validate_launcher(host=m.broker.EXPECTED_HOST, platform="nt", confirm="NO")


def test_task_ready_requires_startup_s4u_highest() -> None:
    assert m.task_ready(
        {
            "exists": True,
            "trigger_at_startup": True,
            "logon_type": "S4U",
            "run_level": "highest",
        }
    )
    assert not m.task_ready(
        {
            "exists": True,
            "trigger_at_startup": True,
            "logon_type": "S4U",
            "run_level": "limited",
        }
    )


def test_elevated_command_is_metadata_only(tmp_path: Path) -> None:
    installation = {
        "release_broker": tmp_path / "desktop_admin_broker.py",
        "metadata_path": tmp_path / "metadata.json",
    }
    args = m.build_elevated_arguments(installation)
    expected = subprocess.list2cmdline(
        [
            str(installation["release_broker"]),
            "register-task-com",
            "--metadata",
            str(installation["metadata_path"]),
        ]
    )
    assert args == expected
    assert "register-task-com" in args
    assert "--metadata" in args
    assert "--command" not in args
    assert "--action" not in args
    assert "password" not in args.casefold()
    assert "token" not in args.casefold()


def test_finalize_requires_verified_privileged_task(monkeypatch, tmp_path: Path) -> None:
    metadata_path = tmp_path / "metadata.json"
    installation = {
        "metadata": {
            "activation_pending": True,
            "requires_uac_activation": True,
        },
        "metadata_path": metadata_path,
    }
    written = {}
    started = {"value": False}
    monkeypatch.setattr(
        m.broker,
        "task_status",
        lambda: {
            "exists": True,
            "trigger_at_startup": True,
            "logon_type": "S4U",
            "run_level": "highest",
        },
    )
    monkeypatch.setattr(m.broker, "now_iso", lambda: "2026-09-21T18:00:00+00:00")
    monkeypatch.setattr(
        m.broker,
        "atomic_json",
        lambda path, payload: written.update({"path": path, "payload": payload}),
    )
    monkeypatch.setattr(
        m.broker,
        "run_task",
        lambda: started.update({"value": True}) or {"run_returncode": 0},
    )
    result = m.finalize(installation)
    assert result["metadata"]["admin_channel_ready"] is True
    assert result["metadata"]["activation_pending"] is False
    assert written["path"] == metadata_path
    assert started["value"] is True
