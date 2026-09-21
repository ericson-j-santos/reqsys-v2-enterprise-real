from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "activate_noteri_free_control_plane.py"
CMD = ROOT / "scripts" / "activate_noteri_free_control_plane.cmd"

def load_module():
    spec = importlib.util.spec_from_file_location("activate_noteri_free_control_plane", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

def test_bootstrap_is_rdc_independent_and_fail_closed():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'EXPECTED_HOST = "Noteri"' in text
    assert 'runner_registration_required' in text
    assert '"rdc_required": False' in text
    assert '"production_touched": False' in text
    assert '"secrets_read": False' in text
    assert ".runner" in text
    assert "read_text" not in text.split("def runner_contract", 1)[1].split("def discover_runner", 1)[0]

def test_bootstrap_reuses_existing_watchdog_contract():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "noteri_control_plane_watchdog.py" in text
    assert "INSTALL-NOTERI-CONTROL-PLANE-WATCHDOG" in text
    assert "Runner.Listener.exe" in text

def test_cmd_is_host_pinned_and_has_no_secret_inputs():
    text = CMD.read_text(encoding="utf-8")
    lowered = text.casefold()
    assert 'not "%computername%"=="noteri"' in lowered
    assert "activate-noteri-free-control-plane" not in lowered
    assert "token" not in lowered
    assert "password" not in lowered
    assert "secret" not in lowered
