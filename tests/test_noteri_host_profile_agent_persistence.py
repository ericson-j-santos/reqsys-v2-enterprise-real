from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "noteri_host_profile_agent_persistence.py"
SPEC = importlib.util.spec_from_file_location("noteri_host_profile_agent_persistence", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_reboot_detection_uses_tolerance() -> None:
    baseline = 1_700_000_000
    assert module.reboot_observed(baseline, baseline + 30) is False
    assert module.reboot_observed(baseline, baseline - 60) is False
    assert module.reboot_observed(baseline, baseline + module.REBOOT_TOLERANCE_SECONDS + 1) is True


def test_runtime_paths_are_under_localappdata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert module.runtime_root() == tmp_path / "ReqSys" / "TodoGlobal24x7"
    assert module.stable_dir().parent == module.runtime_root()
    assert module.metadata_path().parent == module.runtime_root()
    assert module.evidence_path().parent == module.runtime_root()


def test_task_contract_is_boot_s4u_limited() -> None:
    assert module.TASK_TRIGGER_BOOT == 8
    assert module.TASK_LOGON_S4U == 2
    assert module.TASK_RUNLEVEL_LUA == 0
    assert module.TASK_NAME == "ReqSys-NoteriHostProfileAgent"


def test_access_denied_detection_recognizes_windows_hresult() -> None:
    exc = RuntimeError("pywintypes.com_error nested -2147024891")
    assert module._is_access_denied(exc) is True


def test_headless_preconditions_accept_explicit_admin_authorization() -> None:
    module.validate_headless_preconditions(
        host="Noteri",
        platform="nt",
        elevated=True,
        confirm=module.HEADLESS_CONFIRM,
    )


def test_headless_preconditions_fail_closed_without_admin() -> None:
    try:
        module.validate_headless_preconditions(
            host="Noteri",
            platform="nt",
            elevated=False,
            confirm=module.HEADLESS_CONFIRM,
        )
    except RuntimeError as exc:
        assert str(exc) == "admin_elevation_required"
    else:
        raise AssertionError("headless deve exigir elevação administrativa")


def test_headless_preconditions_require_exact_confirmation() -> None:
    try:
        module.validate_headless_preconditions(
            host="Noteri",
            platform="nt",
            elevated=True,
            confirm="INVALID",
        )
    except RuntimeError as exc:
        assert "confirmação headless inválida" in str(exc)
    else:
        raise AssertionError("confirmação inválida deve falhar")


def test_control_arguments_pin_runtime_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    args = module.control_arguments(tmp_path / "noteri_host_profile_agent_control.py")
    assert f'--profile-path "{module.profile_path()}"' in args
    assert f'--audit-path "{module.audit_path()}"' in args
    assert f'--state-path "{module.agent_state_path()}"' in args
