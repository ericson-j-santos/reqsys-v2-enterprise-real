from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "activate_desktop_free_control_plane.py"


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
