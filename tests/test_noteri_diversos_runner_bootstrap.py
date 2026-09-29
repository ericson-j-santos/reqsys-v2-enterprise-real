from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap_noteri_diversos_runner.py"
CONFIG = ROOT / "scripts" / "configure_noteri_diversos_runner_risk3.py"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-diversos-runner-bootstrap.yml"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"


def load_bootstrap():
    spec = importlib.util.spec_from_file_location("bootstrap_noteri_diversos_runner", BOOTSTRAP)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_bootstrap_is_exact_repo_scoped_and_host_pinned() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'EXPECTED_HOST = "Noteri"' in text
    assert 'REPOSITORY = "ericson-j-santos/diversos"' in text
    assert 'RUNNER_NAME = "Noteri-diversos"' in text
    assert 'CUSTOM_LABELS = ("noteri", "diversos-dev")' in text
    assert 'RUNNER_VERSION = "2.337.0"' in text
    assert 'RUNNER_ASSET_SHA256 = "1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc"' in text
    assert "registration-token" in text
    assert "registration_token_persisted" in text
    assert "registration_token_logged" in text
    assert "print(token)" not in text


def test_bootstrap_negative_host_control() -> None:
    module = load_bootstrap()
    with pytest.raises(module.BootstrapError, match="host_not_allowed"):
        module.validate_context(host="OTHER-HOST", os_name="nt")


def test_required_runner_labels_are_fail_closed() -> None:
    module = load_bootstrap()
    assert module.labels_ok(["self-hosted", "Windows", "X64", "noteri", "diversos-dev"])
    assert not module.labels_ok(["self-hosted", "Windows", "X64", "noteri"])
    assert not module.labels_ok(["self-hosted", "Linux", "X64", "noteri", "diversos-dev"])


def test_risk3_action_is_exact_temporary_and_dev_only() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    assert 'ACTION_ID = "reqsys.noteri-diversos-runner-bootstrap.dev"' in text
    assert 'SCOPE = "repo://ericson-j-santos/diversos/actions/runner/noteri-diversos"' in text
    assert 'AUTHORIZATION_REF = "chat-20260928-diversos-noteri-dev"' in text
    assert 'DEFAULT_TTL_MINUTES = 30' in text
    assert '"environment": "dev"' in text
    assert "ttl_minutes > 30" in text
    assert "owner_fingerprint" in text


def test_workflow_uses_governed_session_risk3_and_pinned_runtime() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in text
    assert "session_launcher.py" in text
    assert "SESSION_LAUNCH_OK" in text
    assert "--require-runner-version-preflight" in text
    assert "owner_risk3_gateway.py" in text
    assert "reqsys.noteri-diversos-runner-bootstrap.dev" in text
    assert "repo://ericson-j-santos/diversos/actions/runner/noteri-diversos" in text
    assert "python-3.12.10-embed-amd64.zip" in text
    assert "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3" in text
    assert "actions/setup-python@" not in text
    assert "production_touched" in text
    assert "replay_idempotent" in text


def test_gateway_exposes_only_exact_diversos_runner_command() -> None:
    text = GATEWAY.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/reqsys run noteri-diversos-runner-bootstrap'" in text
    assert "'/reqsys run noteri-diversos-runner-bootstrap')" in text
    assert "target='noteri-diversos-runner-bootstrap.yml'" in text
    assert "steps.route.outputs.target == 'noteri-diversos-runner-bootstrap.yml'" in text
    assert "-f repository=diversos" not in text
    assert "-f runner=" not in text
