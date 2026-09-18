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
