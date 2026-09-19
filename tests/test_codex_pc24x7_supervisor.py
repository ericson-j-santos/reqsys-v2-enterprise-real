from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "codex_pc24x7_supervisor.py"
SPEC = importlib.util.spec_from_file_location("codex_pc24x7_supervisor", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def profile() -> dict[str, str]:
    return {
        "CODEX_OLLAMA_MODEL": "gemma4:31b-cloud",
        "CODEX_OLLAMA_GATEWAY_MODEL": "gemma4:31b-cloud",
        "CODEX_OLLAMA_FALLBACK_MODEL": "gemma4:26b-q8-code",
        "CODEX_OLLAMA_BASE_URL": "http://127.0.0.1:11434",
    }


def test_profile_requires_loopback_and_aligned_model() -> None:
    m.validate_profile(profile())
    invalid = profile()
    invalid["CODEX_OLLAMA_BASE_URL"] = "http://10.0.0.5:11434"
    with pytest.raises(m.SupervisorError, match="loopback"):
        m.validate_profile(invalid)
    invalid = profile()
    invalid["CODEX_OLLAMA_GATEWAY_MODEL"] = "outro"
    with pytest.raises(m.SupervisorError, match="idênticos"):
        m.validate_profile(invalid)


def test_gateway_and_backend_are_loopback_only(tmp_path: Path) -> None:
    gw = m.build_gateway_env(profile())
    be = m.build_backend_env(profile(), tmp_path, "a" * 40)
    assert gw["REQSYS_OLLAMA_BASE_URL"] == "http://127.0.0.1:11434"
    assert gw["REQSYS_AUTH_REQUIRED"] == "false"
    assert be["CODEX_OLLAMA_GATEWAY_URL"] == "http://127.0.0.1:8008"
    assert be["APP_ENV"] == "development"
    assert be["PUBLIC_ENVIRONMENT"] == "development"


def test_task_action_contains_no_secret_values(tmp_path: Path) -> None:
    action = m._task_action(
        Path(r"C:\Python\python.exe"),
        tmp_path / "supervisor.py",
        tmp_path / "metadata.json",
    )
    assert "password" not in action.casefold()
    assert "token" not in action.casefold()
    assert "watch" in action


def test_runtime_status_fails_closed_without_install(tmp_path: Path) -> None:
    status = m.runtime_status(tmp_path / "missing.json")
    assert status["installed"] is False
    assert status["runtime_healthy"] is False


def test_install_falls_back_to_logon_when_startup_task_denied(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "backend").mkdir(parents=True)
    (source / "docs/ollama-local-gateway/bootstrap-files/src").mkdir(parents=True)
    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    monkeypatch.setattr(m, "require_windows_desktop", lambda: m.EXPECTED_HOST)
    monkeypatch.setattr(m, "read_profile", profile)
    monkeypatch.setattr(m, "windows_boot_epoch", lambda: 100)
    monkeypatch.setattr(m, "_copy_release", lambda source_root, release_root: (
        (release_root / "scripts").mkdir(parents=True, exist_ok=True),
        (release_root / "scripts" / "codex_pc24x7_supervisor.py").write_text("x", encoding="utf-8"),
    ))
    monkeypatch.setattr(
        m,
        "_run_schtasks",
        lambda args: subprocess.CompletedProcess(["schtasks"], 1, stdout="", stderr="Access is denied"),
    )
    observed = {}
    monkeypatch.setattr(m, "_install_run_key", lambda action: observed.setdefault("action", action))
    monkeypatch.setattr(m.subprocess, "Popen", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        m,
        "runtime_status",
        lambda path: {"runtime_healthy": True, "ok": True},
    )
    monkeypatch.setattr(m, "task_status", lambda: {"exists": False})
    monkeypatch.setattr(m, "run_key_status", lambda: {"configured": True})

    result = m.install(
        source,
        source_sha="a" * 40,
        python_executable=python,
        runtime_root=tmp_path / "runtime",
    )

    assert result["ok"] is True
    assert result["headless_24x7"] is False
    assert result["metadata"]["persistence_mode"] == "hkcu_run_at_logon"
    assert result["metadata"]["requires_user_logon"] is True
    assert "watch" in observed["action"]


def test_postboot_requires_real_reboot_for_headless_evidence(monkeypatch, tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    metadata = runtime / "metadata.json"
    metadata.write_text(
        '{"baseline_boot_epoch":100,"runtime_root":"' + str(runtime).replace("\\", "\\\\") +
        '","persistence_mode":"task_at_startup_no_password","requires_user_logon":false}',
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "windows_boot_epoch", lambda: 100)
    monkeypatch.setattr(m, "runtime_status", lambda path: {"runtime_healthy": True})
    code, payload = m.postboot_check(metadata, True)
    assert code == 4
    assert payload["reboot_observed"] is False
    assert payload["ready_postboot"] is False
