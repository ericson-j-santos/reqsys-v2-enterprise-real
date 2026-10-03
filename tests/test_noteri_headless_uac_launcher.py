from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "noteri_headless_uac_launcher.py"
SCRIPTS = str(MODULE_PATH.parent)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
SPEC = importlib.util.spec_from_file_location("noteri_headless_uac_launcher", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_launcher_requires_exact_confirmation() -> None:
    with pytest.raises(RuntimeError, match="confirmação UAC inválida"):
        module.validate_launcher(host="Noteri", platform="nt", confirm="INVALID")


def test_launcher_rejects_other_host() -> None:
    with pytest.raises(RuntimeError, match="somente no host Noteri"):
        module.validate_launcher(
            host="DESKTOP-PDQK954",
            platform="nt",
            confirm=module.LAUNCH_CONFIRM,
        )


def test_build_elevated_arguments_is_fixed_to_headless_installer(tmp_path: Path) -> None:
    args = module.build_elevated_arguments(tmp_path)
    assert "noteri_host_profile_agent_persistence.py" in args
    assert "install-headless" in args
    assert persistence_confirm() in args
    assert str(tmp_path.resolve()) in args


def persistence_confirm() -> str:
    return module.persistence.HEADLESS_CONFIRM
