import importlib.util

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "activate_desktop_free_control_plane.py"
SPEC = importlib.util.spec_from_file_location("activate_desktop_free_control_plane", SCRIPT)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_contract_is_host_repo_and_labels_pinned() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'EXPECTED_HOST = "DESKTOP-PDQK954"' in text
    assert 'REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"' in text
    assert 'RUNNER_NAME = "DESKTOP-PDQK954"' in text
    assert 'RUNNER_LABELS = "pc24x7,reqsys-dev"' in text


def test_runner_supply_chain_is_fixed() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'RUNNER_VERSION = "2.337.0"' in text
    assert 'RUNNER_ASSET_SHA256 = "1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc"' in text
    assert "actions/runner/releases/download/" in text
    assert "runner_digest_mismatch" in text


def test_registration_token_is_ephemeral_and_never_reported() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "registration-token" in text
    assert 'registration_token_persisted": False' in text
    assert 'registration_token_logged": False' in text
    assert 'token = ""' in text


def test_bootstrap_reuses_desktop_watchdog() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'desktop_control_plane_watchdog.py' in text
    assert 'INSTALL-DESKTOP-CONTROL-PLANE-WATCHDOG' in text
    assert "Runner.Listener.exe" in text


def test_bootstrap_has_no_arbitrary_target_inputs() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "parser.add_argument(\"--repository\"" not in text
    assert "parser.add_argument(\"--labels\"" not in text
    assert "parser.add_argument(\"--runner-name\"" not in text
    assert "parser.add_argument(\"--token\"" not in text


def test_runtime_active_requires_github_registry_online_and_labels() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "runner_registry_snapshot" in text
    assert "wait_runner_registry_online" in text
    assert 'repos/{REPOSITORY}/actions/runners' in text
    assert 'REQUIRED_RUNNER_LABELS = ("self-hosted", "Windows", "X64", "pc24x7", "reqsys-dev")' in text
    assert '"runner_registry_missing"' in text
    assert '"runner_github_offline"' in text
    assert '"runner_labels_mismatch"' in text
    assert 'state == "runtime_active"' in text


def test_noninteractive_mode_fails_closed_before_browser_auth() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'parser.add_argument("--non-interactive-auth", action="store_true")' in text
    assert "allow_interactive=not args.non_interactive_auth" in text
    assert "allow_interactive_auth=not args.non_interactive_auth" in text
    assert "if not allow_interactive:" in text
    assert "login interativo desabilitado neste modo" in text
    assert "refresh interativo desabilitado" in text


def test_offline_restart_policy_is_narrow_and_fail_closed() -> None:
    offline = {"present": True, "status": "offline", "labels_ok": True}
    assert m.should_restart_offline_runner(offline, True) is True
    assert m.should_restart_offline_runner({**offline, "status": "online"}, True) is False
    assert m.should_restart_offline_runner({**offline, "present": False}, True) is False
    assert m.should_restart_offline_runner({**offline, "labels_ok": False}, True) is False
    assert m.should_restart_offline_runner(offline, False) is False


def test_bootstrap_delegates_process_identity_and_restart_to_watchdog() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "watchdog.runner_running(root)" in text
    assert "watchdog.start_runner(root, _runner_log_path(root))" in text
    assert "watchdog.restart_runner(root, _runner_log_path(root))" in text
    assert "runner_restarted_offline" in text
    assert "runner_restart_previous_listener_pid" in text

def _make_registered_runner(tmp_path: Path) -> Path:
    runner = tmp_path / "runner"
    (runner / "bin").mkdir(parents=True)
    (runner / "config.cmd").write_text("@echo off\n", encoding="utf-8")
    (runner / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (runner / "bin" / "Runner.Listener.exe").write_bytes(b"runner")
    (runner / ".runner").write_text("{}", encoding="utf-8")
    return runner


def test_missing_registry_repair_authorizes_before_local_mutation(monkeypatch, tmp_path: Path) -> None:
    runner = _make_registered_runner(tmp_path)
    marker = runner / ".runner"
    order: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        m,
        "registration_token",
        lambda gh, allow_interactive=True: order.append(("token", marker.exists())) or ("t" * 32),
    )

    class FakeWatchdog:
        @staticmethod
        def stop_runner(root):
            order.append(("stop", marker.exists()))
            assert root == runner.resolve()
            return {
                "status": "stopped",
                "stopped": True,
                "previous_listener_pid": 4321,
                "termination_scope": "exact_runner_home",
            }

    monkeypatch.setattr(m, "_load_watchdog_runtime", lambda: FakeWatchdog)

    def fake_configure(root, token):
        order.append(("configure", marker.exists()))
        assert root == runner.resolve()
        assert token == "t" * 32
        marker.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(m, "configure_runner_with_token", fake_configure)

    result = m.repair_missing_registry(
        runner,
        Path("gh"),
        allow_interactive_auth=False,
    )

    assert order == [("token", True), ("stop", True), ("configure", False)]
    assert result["registered"] is True
    assert result["previous_listener_pid"] == 4321
    assert marker.is_file()


def test_missing_registry_repair_preserves_local_contract_when_authorization_fails(
    monkeypatch, tmp_path: Path
) -> None:
    runner = _make_registered_runner(tmp_path)
    marker = runner / ".runner"

    def denied(*args, **kwargs):
        raise m.ActivationError(
            "github_runner_admin_permission_required",
            "sem permissão",
        )

    monkeypatch.setattr(m, "registration_token", denied)
    monkeypatch.setattr(
        m,
        "_load_watchdog_runtime",
        lambda: (_ for _ in ()).throw(AssertionError("must not stop before authorization")),
    )

    with pytest.raises(m.ActivationError, match="sem permissão"):
        m.repair_missing_registry(
            runner,
            Path("gh"),
            allow_interactive_auth=False,
        )

    assert marker.is_file()


def test_main_path_can_repair_local_contract_missing_from_github_registry() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "initial_registry = wait_runner_registry_online" in text
    assert "repair_missing_registry(" in text
    assert '"runner_registry_repaired_missing"' in text

