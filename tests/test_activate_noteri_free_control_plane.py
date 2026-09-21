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
    assert '"rdc_required": False' in text
    assert '"production_touched": False' in text
    assert '"registration_token_persisted": False' in text
    assert '"registration_token_logged": False' in text
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
    assert "--confirm activate-noteri-free-control-plane" in lowered
    assert "token" not in lowered
    assert "password" not in lowered
    assert "secret" not in lowered


def test_bootstrap_auto_registers_official_pinned_runner_without_logging_token():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'RUNNER_VERSION = "2.337.0"' in text
    assert 'RUNNER_ASSET_SHA256 = "1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc"' in text
    assert 'actions-runner-win-x64-' in text
    assert 'registration-token' in text
    assert '"--labels", RUNNER_LABELS' in text
    assert 'RUNNER_LABELS = "noteri,reqsys-dev"' in text
    assert '"--replace"' in text
    assert 'registration_token_persisted' in text
    assert 'registration_token_logged' in text
    assert 'print(token)' not in text
    assert 'emit({"token"' not in text


def test_bootstrap_can_prepare_github_cli_without_rdc():
    text = SCRIPT.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert '"GitHub.cli"' in text
    assert '"winget"' in text
    assert '"auth", "login"' in normalized
    assert '"--web"' in text
    assert 'rdc_required' in text


def test_bootstrap_refreshes_repo_scope_and_selects_expected_account():
    text = SCRIPT.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert 'EXPECTED_GITHUB_LOGIN = "ericson-j-santos"' in text
    assert '"auth", "switch"' in normalized
    assert '"--user", EXPECTED_GITHUB_LOGIN' in normalized
    assert '"auth", "refresh"' in normalized
    assert '"--scopes", "repo"' in normalized
    assert 'env.pop("GH_TOKEN", None)' in text
    assert 'env.pop("GITHUB_TOKEN", None)' in text
    assert 'github_account_mismatch' in text


def test_bootstrap_supports_dedicated_native_windows_service_runner():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'HEADLESS_RUNNER_NAME = "NoteriHeadless"' in text
    assert 'HEADLESS_RUNNER_LABELS = "noteri-headless,reqsys-dev"' in text
    assert 'HEADLESS_RUNNER_HOME = Path(r"C:\\actions-runner-noteri-headless")' in text
    assert '"--runasservice"' in text
    assert "RunnerService.exe" in text
    assert '".service"' in text
    assert '"headless-service-status"' in text
    assert "windowslogonpassword" not in text.casefold()
    assert "NETWORK SERVICE" not in text


def test_headless_service_registration_is_admin_gated_and_token_stays_in_memory():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "administrator_required" in text
    assert "if run_as_service and not is_admin()" in text
    assert "registration_token_consumed_in_memory" in text
    assert "registration_token_persisted" in text
    assert "registration_token_logged" in text
