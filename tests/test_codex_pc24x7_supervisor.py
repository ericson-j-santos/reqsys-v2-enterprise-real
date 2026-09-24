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


def test_task_action_contains_no_secret_values_and_stays_short(tmp_path: Path) -> None:
    launcher = m._write_launcher(tmp_path)
    action = m._task_action(Path(r"C:\Python\python.exe"), launcher)
    assert "password" not in action.casefold()
    assert "token" not in action.casefold()
    assert len(action) < 261
    launcher_text = launcher.read_text(encoding="utf-8")
    assert "watch" in launcher_text
    assert "metadata.json" in launcher_text


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
        "_register_task_via_base_python",
        lambda **kwargs: subprocess.CompletedProcess(["python"], 1, stdout="", stderr="Access is denied"),
    )
    monkeypatch.setattr(m, "probe_ollama", lambda: None)
    monkeypatch.setattr(m, "probe_gateway", lambda: None)
    monkeypatch.setattr(m, "probe_backend", lambda: None)
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
    assert "run.py" in observed["action"]
    launcher = tmp_path / "runtime" / "run.py"
    assert "watch" in launcher.read_text(encoding="utf-8")


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


def test_windows_encoding_dependency_is_imported() -> None:
    assert hasattr(m, "locale")
    assert callable(m.locale.getpreferredencoding)

def test_mcp_bridge_env_is_fail_closed_and_loopback_only(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_MCP_BEARER_TOKEN", raising=False)
    with pytest.raises(m.SupervisorError, match="mcp_bearer_token_not_configured"):
        m.build_mcp_bridge_env(profile())

    env = m.build_mcp_bridge_env(
        profile(),
        {
            "OLLAMA_MCP_BEARER_TOKEN": "secret-test-value",
            "PATH": r"C:\\Windows\\System32",
            "GITHUB_TOKEN": "must-not-propagate",
            "UNRELATED": "must-not-propagate",
        },
    )
    assert env["OLLAMA_MCP_GATEWAY_URL"] == "http://127.0.0.1:8008"
    assert env["OLLAMA_MCP_ALLOWED_MODELS"] == "gemma4:31b-cloud,gemma4:26b-q8-code"
    assert env["OLLAMA_MCP_DEFAULT_MODEL"] == "gemma4:31b-cloud"
    assert env["OLLAMA_MCP_FALLBACK_MODEL"] == "gemma4:26b-q8-code"
    assert env["PATH"] == r"C:\\Windows\\System32"
    assert "GITHUB_TOKEN" not in env
    assert "UNRELATED" not in env


def test_copy_release_includes_mcp_bridge(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "backend").mkdir(parents=True)
    (source / "docs/ollama-local-gateway/bootstrap-files/src").mkdir(parents=True)
    bridge = source / "services" / "ollama-mcp-bridge"
    bridge.mkdir(parents=True)
    (bridge / "server.py").write_text("print('bridge')\n", encoding="utf-8")
    (bridge / "requirements.txt").write_text("mcp>=2.0,<3.0\n", encoding="utf-8")

    release = tmp_path / "runtime" / "releases" / ("b" * 40)
    m._copy_release(source, release)

    assert (release / "mcp_bridge" / "server.py").is_file()
    assert (release / "mcp_bridge" / "requirements.txt").read_text(encoding="utf-8") == "mcp>=2.0,<3.0\n"


def test_runtime_status_requires_mcp_bridge_health(monkeypatch, tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    metadata = runtime / "metadata.json"
    metadata.write_text(
        '{"runtime_root":"' + str(runtime).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "probe_ollama", lambda: {"ok": True})
    monkeypatch.setattr(m, "probe_gateway", lambda: {"ok": True})
    monkeypatch.setattr(m, "probe_backend", lambda: {"ok": True})
    monkeypatch.setattr(m, "task_status", lambda: {"exists": True})
    monkeypatch.setattr(m, "run_key_status", lambda: {"configured": False})

    monkeypatch.setattr(m, "probe_mcp_bridge", lambda: None)
    blocked = m.runtime_status(metadata)
    assert blocked["runtime_healthy"] is False
    assert blocked["health"]["mcp_bridge"] is None

    monkeypatch.setattr(
        m,
        "probe_mcp_bridge",
        lambda: {
            "ok": True,
            "service": "reqsys-ollama-mcp-bridge",
            "bind": "127.0.0.1",
            "port": 8010,
            "auth_configured": True,
            "secret_exposed": False,
        },
    )
    healthy = m.runtime_status(metadata)
    assert healthy["runtime_healthy"] is True
    assert healthy["health"]["mcp_bridge"]["port"] == 8010

def test_mcp_bridge_probe_requires_identified_health(monkeypatch) -> None:
    monkeypatch.setattr(m, "_port_open", lambda port: port == 8010)
    monkeypatch.setattr(
        m,
        "_request_json",
        lambda *args, **kwargs: (
            200,
            {
                "status": "ok",
                "service": "reqsys-ollama-mcp-bridge",
                "transport": "streamable-http",
                "mcp_path": "/mcp",
                "auth_configured": True,
                "secret_exposed": False,
            },
        ),
    )
    health = m.probe_mcp_bridge()
    assert health is not None
    assert health["service"] == "reqsys-ollama-mcp-bridge"

    monkeypatch.setattr(
        m,
        "_request_json",
        lambda *args, **kwargs: (
            200,
            {
                "status": "ok",
                "service": "unexpected-service",
                "auth_configured": True,
                "secret_exposed": False,
            },
        ),
    )
    assert m.probe_mcp_bridge() is None

