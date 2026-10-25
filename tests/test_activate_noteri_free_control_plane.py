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

def test_runtime_active_requires_remote_registry_and_exact_runner_identity():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "runner_registry_snapshot" in text
    assert "wait_runner_registry_online" in text
    assert 'REQUIRED_RUNNER_LABELS = ("self-hosted", "Windows", "X64", "noteri", "reqsys-dev")' in text
    assert "watchdog.runner_running(root)" in text
    assert "watchdog.runner_process_snapshot(root)" in text
    assert '"runner_registry_missing"' in text
    assert '"runner_github_offline"' in text
    assert '"runner_labels_mismatch"' in text
    assert 'state == "runtime_active"' in text


def test_noninteractive_auth_fails_closed_before_web_login():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'parser.add_argument("--non-interactive-auth", action="store_true")' in text
    assert "allow_interactive=not args.non_interactive_auth" in text
    assert "allow_interactive_auth=not args.non_interactive_auth" in text
    assert "login interativo desabilitado neste modo" in text
    assert "refresh interativo desabilitado" in text


def test_missing_registry_repair_policy_is_narrow():
    module = load_module()
    assert module.should_repair_missing_registry({"present": False}, True) is True
    assert module.should_repair_missing_registry({"present": True}, True) is False
    assert module.should_repair_missing_registry({"present": False}, False) is False


def test_repair_missing_registration_acquires_tokens_before_mutation(monkeypatch, tmp_path):
    module = load_module()
    runner = tmp_path / "runner"
    runner.mkdir()
    events = []
    monkeypatch.setattr(module, "remove_token", lambda *a, **k: events.append("remove_token") or "R" * 24)
    monkeypatch.setattr(module, "registration_token", lambda *a, **k: events.append("registration_token") or "G" * 24)
    monkeypatch.setattr(
        module,
        "stop_runner",
        lambda root: events.append("stop") or {
            "previous_listener_pid": 123,
            "termination_scope": "exact_runner_home",
        },
    )
    monkeypatch.setattr(module, "_remove_runner_with_token", lambda root, token: events.append("remove_local"))
    monkeypatch.setattr(module, "_register_runner_with_token", lambda root, token: events.append("register"))
    result = module.repair_missing_registration(runner, Path("gh"), allow_interactive_auth=False)
    assert events == ["remove_token", "registration_token", "stop", "remove_local", "register"]
    assert result["repaired"] is True
    assert result["termination_scope"] == "exact_runner_home"


def test_registration_token_failure_does_not_stop_or_mutate_runner(monkeypatch, tmp_path):
    module = load_module()
    runner = tmp_path / "runner"
    runner.mkdir()
    events = []
    monkeypatch.setattr(module, "remove_token", lambda *a, **k: events.append("remove_token") or "R" * 24)

    def registration_failure(*args, **kwargs):
        events.append("registration_token")
        raise module.ActivationError("github_runner_admin_permission_required", "blocked")

    monkeypatch.setattr(module, "registration_token", registration_failure)
    monkeypatch.setattr(module, "stop_runner", lambda root: events.append("stop"))
    try:
        module.repair_missing_registration(runner, Path("gh"), allow_interactive_auth=False)
        assert False, "repair should fail closed"
    except module.ActivationError as exc:
        assert exc.state == "github_runner_admin_permission_required"
    assert events == ["remove_token", "registration_token"]

