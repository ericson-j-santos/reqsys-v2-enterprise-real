from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "desktop_dedicated_listener_recovery.py"
SPEC = importlib.util.spec_from_file_location("desktop_dedicated_listener_recovery", SCRIPT)
assert SPEC and SPEC.loader
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)

SOURCE_REPOSITORY = subject.SOURCE_REPOSITORY


def make_home(tmp_path: Path) -> Path:
    home = tmp_path / "DesktopPC24x7" / "GitHubRunner"
    (home / "bin").mkdir(parents=True)
    (home / ".runner").write_text("opaque-marker", encoding="utf-8")
    (home / "run.cmd").write_text("@echo off", encoding="utf-8")
    (home / "bin" / subject.LISTENER_NAME).write_bytes(b"pe-marker")
    return home


def snapshot(home: Path, pids: list[int]) -> dict:
    expected = str((home / "bin" / subject.LISTENER_NAME).resolve())
    return {
        "expected_executable": expected,
        "matching_pids": list(pids),
        "unresolved_pids": [],
        "observed": [{"pid": pid, "path": expected} for pid in pids],
    }


def identity_reader_factory(
    target_states: list[tuple[str, bool]],
):
    calls: list[tuple[str, int]] = []

    def read(repository: str, runner_id: int) -> dict:
        calls.append((repository, runner_id))
        if repository == SOURCE_REPOSITORY:
            return {
                "id": subject.SOURCE_RUNNER_ID,
                "name": subject.SOURCE_RUNNER_NAME,
                "status": "online",
                "busy": True,
            }
        status, busy = target_states.pop(0) if target_states else ("offline", False)
        return {
            "id": subject.TARGET_RUNNER_ID,
            "name": subject.TARGET_RUNNER_NAME,
            "status": status,
            "busy": busy,
        }

    return read, calls


def execute(
    tmp_path: Path,
    *,
    mode: str,
    confirm: str,
    target_states: list[tuple[str, bool]],
    pids: list[int],
    after_pids: list[int] | None = None,
    host: str = subject.SOURCE_HOST,
    runner_name: str = subject.SOURCE_RUNNER_NAME,
    repository: str = SOURCE_REPOSITORY,
    version: str = "2.337.0.0",
    starter=None,
    stopper=None,
    target_home: Path | None = None,
):
    home = target_home or make_home(tmp_path)
    reader, calls = identity_reader_factory(target_states)
    started: list[Path] = []
    stopped: list[int] = []
    observed_after = snapshot(home, after_pids if after_pids is not None else pids)
    result = subject.execute(
        mode=mode,
        confirm=confirm,
        evidence_file=tmp_path / "evidence.json",
        host=host,
        platform="nt",
        runner_name=runner_name,
        repository=repository,
        runner_home=home,
        identity_reader=reader,
        snapshot_reader=lambda _: snapshot(home, pids),
        version_reader=lambda _: version,
        starter=starter or (lambda path: started.append(path)),
        stopper=stopper or (lambda pid: stopped.append(pid)),
        wait_reader=lambda _: observed_after,
    )
    return result, calls, started, stopped, home


def test_readonly_validates_fixed_identity_and_reports_exact_process_path(tmp_path: Path) -> None:
    result, calls, started, stopped, home = execute(
        tmp_path,
        mode=subject.READONLY_MODE,
        confirm=subject.READONLY_CONFIRM,
        target_states=[("offline", False)],
        pids=[],
    )

    assert result["ok"] is True
    assert result["result"] == "DESKTOP_DEDICATED_LISTENER_READONLY_OK"
    assert result["source_runner_id"] == 22
    assert result["target_runner_id"] == 2
    assert result["target_repository"] == subject.TARGET_REPOSITORY
    assert result["target_runner_name"] == "DESKTOP-PDQK954-runtime"
    assert result["target_listener_executable"] == str((home / "bin" / subject.LISTENER_NAME).resolve())
    assert result["target_listener_pids"] == []
    assert result["action_count"] == 0
    assert started == [] and stopped == []
    assert calls == [
        (subject.SOURCE_REPOSITORY, subject.SOURCE_RUNNER_ID),
        (subject.TARGET_REPOSITORY, subject.TARGET_RUNNER_ID),
    ]
    payload = json.dumps(result, sort_keys=True)
    assert "opaque-marker" not in payload
    assert "token" not in payload.casefold()
    assert result["process_arguments_observed"] is False
    assert result["raw_logs_read"] is False


def test_recovery_starts_only_once_when_target_is_offline_and_absent(tmp_path: Path) -> None:
    result, _, started, stopped, _ = execute(
        tmp_path,
        mode=subject.RECOVERY_MODE,
        confirm=subject.RECOVERY_CONFIRM,
        target_states=[("offline", False), ("online", False)],
        pids=[],
        after_pids=[101],
    )

    assert result["ok"] is True
    assert result["result"] == "DESKTOP_DEDICATED_LISTENER_STARTED"
    assert result["action"] == "start"
    assert result["action_count"] == 1
    assert len(started) == 1
    assert stopped == []


def test_recovery_restarts_exact_listener_once_when_registry_is_offline(tmp_path: Path) -> None:
    result, _, started, stopped, _ = execute(
        tmp_path,
        mode=subject.RECOVERY_MODE,
        confirm=subject.RECOVERY_CONFIRM,
        target_states=[("offline", False), ("online", False)],
        pids=[101],
        after_pids=[202],
    )

    assert result["ok"] is True
    assert result["result"] == "DESKTOP_DEDICATED_LISTENER_RESTARTED"
    assert result["action"] == "restart"
    assert result["action_count"] == 1
    assert stopped == [101]
    assert len(started) == 1


def test_recovery_is_idempotent_when_exact_listener_is_already_healthy(tmp_path: Path) -> None:
    result, _, started, stopped, _ = execute(
        tmp_path,
        mode=subject.RECOVERY_MODE,
        confirm=subject.RECOVERY_CONFIRM,
        target_states=[("online", False)],
        pids=[101],
    )

    assert result["ok"] is True
    assert result["result"] == "DESKTOP_DEDICATED_LISTENER_ALREADY_HEALTHY"
    assert result["action"] == "none"
    assert result["action_count"] == 0
    assert started == [] and stopped == []


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"host": "Noteri"}, "source_host_mismatch"),
        ({"runner_name": "OTHER-RUNNER"}, "source_runner_name_mismatch"),
        ({"repository": "other/repo"}, "source_repository_mismatch"),
        ({"confirm": "WRONG"}, "confirmation_invalid"),
    ],
)
def test_recovery_rejects_divergent_source_or_confirmation(
    tmp_path: Path, kwargs: dict, reason: str
) -> None:
    result, _, started, stopped, _ = execute(
        tmp_path,
        mode=subject.RECOVERY_MODE,
        confirm=kwargs.pop("confirm", subject.RECOVERY_CONFIRM),
        target_states=[("offline", False)],
        pids=[],
        **kwargs,
    )
    assert result["ok"] is False
    assert result["block_reason"] == reason
    assert started == [] and stopped == []


def test_recovery_blocks_active_work_before_any_process_action(tmp_path: Path) -> None:
    result, _, started, stopped, _ = execute(
        tmp_path,
        mode=subject.RECOVERY_MODE,
        confirm=subject.RECOVERY_CONFIRM,
        target_states=[("offline", True)],
        pids=[],
    )

    assert result["ok"] is False
    assert result["block_reason"] == "target_runner_active_work"
    assert result["action_count"] == 0
    assert started == [] and stopped == []


def test_recovery_blocks_duplicate_target_listeners(tmp_path: Path) -> None:
    result, _, started, stopped, _ = execute(
        tmp_path,
        mode=subject.RECOVERY_MODE,
        confirm=subject.RECOVERY_CONFIRM,
        target_states=[("offline", False)],
        pids=[101, 102],
    )

    assert result["ok"] is False
    assert result["block_reason"] == "duplicate_target_listener"
    assert result["action_count"] == 0
    assert started == [] and stopped == []


def test_recovery_blocks_invalid_listener_version(tmp_path: Path) -> None:
    result, _, started, stopped, _ = execute(
        tmp_path,
        mode=subject.RECOVERY_MODE,
        confirm=subject.RECOVERY_CONFIRM,
        target_states=[("offline", False)],
        pids=[],
        version="2.328.0.0",
    )

    assert result["ok"] is False
    assert result["block_reason"] == "listener_version_unsupported"
    assert result["action_count"] == 0
    assert started == [] and stopped == []


def test_recovery_blocks_target_identity_divergence(tmp_path: Path) -> None:
    home = make_home(tmp_path)
    calls = []

    def reader(repository: str, runner_id: int) -> dict:
        calls.append((repository, runner_id))
        if repository == subject.SOURCE_REPOSITORY:
            return {"id": 22, "name": subject.SOURCE_RUNNER_NAME, "status": "online", "busy": True}
        return {"id": 2, "name": "WRONG-TARGET", "status": "offline", "busy": False}

    result = subject.execute(
        mode=subject.RECOVERY_MODE,
        confirm=subject.RECOVERY_CONFIRM,
        evidence_file=tmp_path / "evidence.json",
        host=subject.SOURCE_HOST,
        platform="nt",
        runner_name=subject.SOURCE_RUNNER_NAME,
        repository=subject.SOURCE_REPOSITORY,
        runner_home=home,
        identity_reader=reader,
        snapshot_reader=lambda _: snapshot(home, []),
        version_reader=lambda _: "2.337.0.0",
        starter=lambda _: pytest.fail("start must be blocked"),
        stopper=lambda _: pytest.fail("stop must be blocked"),
    )

    assert result["ok"] is False
    assert result["block_reason"] == "runner_registry_identity_mismatch"
    assert calls == [
        (subject.SOURCE_REPOSITORY, subject.SOURCE_RUNNER_ID),
        (subject.TARGET_REPOSITORY, subject.TARGET_RUNNER_ID),
    ]


def test_static_contract_does_not_expose_mutating_or_raw_observation_paths() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
    assert "activate_desktop_runtime_runner.py" not in raw
    for forbidden in (
        "config.cmd",
        "schtasks",
        "sc.exe",
        "netsh",
        "icacls",
        "safe.directory",
        "shell=True",
        "capture_output",
    ):
        assert forbidden not in raw
    for required in (
        "DESKTOP-PDQK954",
        "desktop-pc24x7-runtime",
        "TARGET_RUNNER_ID = 2",
        "TARGET_HOME_SUFFIX = Path(\"DesktopPC24x7\") / \"GitHubRunner\"",
        "process_arguments_observed",
        "raw_logs_read",
        "stdout=subprocess.DEVNULL",
        "stderr=subprocess.DEVNULL",
    ):
        assert required in raw
