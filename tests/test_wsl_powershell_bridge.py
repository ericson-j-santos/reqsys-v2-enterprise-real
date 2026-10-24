from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "wsl_powershell_bridge.py"
SPEC = importlib.util.spec_from_file_location("wsl_powershell_bridge", MODULE)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

ACTIVATOR = ROOT / "scripts" / "activate_desktop_admin_broker_from_wsl.ps1"
ARGS = ["-Confirm", "ACTIVATE-REQSYS-DESKTOP-ADMIN-BROKER"]


def policy() -> dict:
    return {
        "schema_version": "1",
        "max_timeout_seconds": 300,
        "scripts": {
            "scripts/activate_desktop_admin_broker_from_wsl.ps1": {
                "arguments": ARGS,
                "environment": "local/DEV",
                "interactive_uac": True,
            }
        },
    }


def test_wsl_detection_accepts_interop_and_rejects_plain_linux() -> None:
    assert m.is_wsl(environ={"WSL_INTEROP": "/run/WSL/1_interop"}, release="linux")
    assert m.is_wsl(environ={}, release="5.15.0-microsoft-standard-WSL2")
    assert not m.is_wsl(environ={}, release="6.8.0-generic")


def test_exact_allowlisted_script_and_arguments_are_accepted() -> None:
    script, relative, rule, timeout = m.validate_request(
        policy(),
        repo_root=ROOT,
        requested_script=ACTIVATOR,
        script_args=ARGS,
        timeout_seconds=180,
    )
    assert script == ACTIVATOR.resolve()
    assert relative == "scripts/activate_desktop_admin_broker_from_wsl.ps1"
    assert rule["interactive_uac"] is True
    assert timeout == 180


@pytest.mark.parametrize(
    ("requested", "arguments", "reason"),
    [
        (ACTIVATOR, ["-Confirm", "wrong"], "script_arguments_not_allowlisted"),
        (ROOT / "scripts" / "desktop_admin_broker.py", ARGS, "script_extension_invalid"),
        (ROOT.parent / "outside.ps1", ARGS, "script_outside_repository"),
    ],
)
def test_request_fails_closed(requested: Path, arguments: list[str], reason: str) -> None:
    with pytest.raises(m.BridgeError, match=reason):
        m.validate_request(
            policy(),
            repo_root=ROOT,
            requested_script=requested,
            script_args=arguments,
            timeout_seconds=180,
        )


def test_timeout_is_bounded_by_policy() -> None:
    with pytest.raises(m.BridgeError, match="timeout_out_of_policy"):
        m.validate_request(
            policy(),
            repo_root=ROOT,
            requested_script=ACTIVATOR,
            script_args=ARGS,
            timeout_seconds=301,
        )


def test_environment_removes_secret_bearing_names_and_wslenv() -> None:
    result = m.sanitized_environment(
        {
            "PATH": "/usr/bin",
            "WSL_INTEROP": "/run/WSL/1_interop",
            "WSLENV": "GH_TOKEN/u",
            "GH_TOKEN": "secret",
            "DATABASE_PASSWORD": "secret",
            "SAFE_VALUE": "ok",
        }
    )
    assert result["PATH"] == "/usr/bin"
    assert result["WSL_INTEROP"]
    assert result["SAFE_VALUE"] == "ok"
    assert "WSLENV" not in result
    assert "GH_TOKEN" not in result
    assert "DATABASE_PASSWORD" not in result


def test_command_is_argument_vector_without_inline_command() -> None:
    command = m.build_command(
        Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"),
        r"C:\repo\scripts\activate.ps1",
        ARGS,
    )
    assert "-File" in command
    assert "-Command" not in command
    assert "-EncodedCommand" not in command
    assert command[-2:] == ARGS


def test_activation_script_has_fixed_host_uac_and_task_contract() -> None:
    source = ACTIVATOR.read_text(encoding="utf-8")
    assert 'ExpectedHost = "DESKTOP-PDQK954"' in source
    assert "ACTIVATE-REQSYS-DESKTOP-ADMIN-BROKER" in source
    assert 'Verb = "RunAs"' in source
    assert 'LogonType -eq "S4U"' in source
    assert 'RunLevel -eq "Highest"' in source
    assert "MSFT_TaskBootTrigger" in source
    assert "import win32com.client" in source
    assert "Invoke-Expression" not in source
    assert "ScriptBlock" not in source
    assert "EncodedCommand" not in source
