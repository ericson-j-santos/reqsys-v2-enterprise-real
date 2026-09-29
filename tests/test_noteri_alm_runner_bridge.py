from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "noteri_alm_runner_bridge.py"
RISK3 = ROOT / "scripts" / "configure_noteri_alm_runner_bridge_risk3.py"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-desktop-watchdog-recovery.yml"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_bridge_is_fixed_to_noteri_alm_pr7_and_exact_head() -> None:
    raw = BRIDGE.read_text(encoding="utf-8")
    assert 'EXPECTED_HOST = "Noteri"' in raw
    assert 'TARGET_REPOSITORY = "ericson-j-santos/reqsys-powerplatform-alm"' in raw
    assert "TARGET_PR = 7" in raw
    assert 'EXPECTED_HEAD = "96966d8decc210a98eefa7f0ca437052e8bd5a21"' in raw
    assert 'RUNNER_LABELS = "noteri,reqsys-dev,alm-pr7"' in raw
    assert "RUNNER_SLOTS = 2" in raw
    assert "--ephemeral" in raw
    assert "--disableupdate" in raw


def test_bridge_pins_runner_asset_and_never_reports_registration_token() -> None:
    raw = BRIDGE.read_text(encoding="utf-8")
    assert 'RUNNER_VERSION = "2.337.0"' in raw
    assert "actions-runner-win-x64-" in raw
    assert 'RUNNER_ASSET_SHA256 = "1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc"' in raw
    assert "registration-token" in raw
    assert '"registration_token_persisted": False' in raw
    assert '"registration_token_logged": False' in raw
    assert '"token_exposed": False' in raw
    assert "print(token)" not in raw
    assert '_emit({"token"' not in raw
    assert 'token = ""' not in raw
    assert "del token" in raw


def test_bridge_requires_both_target_workflows_and_independent_readback() -> None:
    module = _load(BRIDGE, "noteri_alm_runner_bridge")
    success = {
        name: {
            "status": "completed",
            "conclusion": "success",
            "head_sha": module.EXPECTED_HEAD,
        }
        for name in module.REQUIRED_WORKFLOWS
    }
    assert module._all_terminal(success)
    assert module._all_success(success)

    failed = dict(success)
    failed[module.REQUIRED_WORKFLOWS[0]] = {
        "status": "completed",
        "conclusion": "failure",
        "head_sha": module.EXPECTED_HEAD,
    }
    assert module._all_terminal(failed)
    assert not module._all_success(failed)

    stale = dict(success)
    stale[module.REQUIRED_WORKFLOWS[1]] = {
        "status": "completed",
        "conclusion": "success",
        "head_sha": "0" * 40,
    }
    assert not module._all_success(stale)


def test_risk3_action_is_exact_temporary_and_dev_only(tmp_path: Path) -> None:
    module = _load(RISK3, "configure_noteri_alm_runner_bridge_risk3")
    assert module.ACTION_ID == "reqsys.noteri-alm-runner-bridge.dev"
    assert module.SCOPE == "repo://ericson-j-santos/reqsys-powerplatform-alm/actions/runner/dev/pr7"
    assert module.COMMAND == ["python", "scripts/noteri_alm_runner_bridge.py"]

    path = tmp_path / "owner-risk3-exceptions.local.json"
    enabled = module.enable(path, 15)
    assert enabled["status"] == "enabled"
    payload = __import__("json").loads(path.read_text(encoding="utf-8"))
    action = payload["actions"][module.ACTION_ID]
    assert action["environment"] == "dev"
    assert action["scope"] == module.SCOPE
    assert action["command"] == module.COMMAND
    disabled = module.disable(path)
    assert disabled["removed"] is True


def test_workflow_exposes_only_fixed_alm_bridge_mode() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "- alm-runner-bootstrap" in raw
    assert "alm-runner-bootstrap:" in raw
    assert "inputs.mode == 'alm-runner-bootstrap'" in raw
    assert "reqsys.noteri-alm-runner-bridge.dev" in raw
    assert "ENABLE-NOTERI-ALM-RUNNER-BRIDGE-ONCE" in raw
    assert "DISABLE-NOTERI-ALM-RUNNER-BRIDGE-ONCE" in raw
    assert "owner_risk3_gateway.py" in raw
    assert "configure_noteri_alm_runner_bridge_risk3.py" in raw
    assert "python312._pth" in raw
    assert '$rulesScripts = Join-Path $env:GITHUB_WORKSPACE "_rules\\\\scripts"' in raw
    assert "RISK3_CLEANUP_NOT_REQUIRED session_not_materialized" in raw
    assert "TARGET_ALM_HEAD: 96966d8decc210a98eefa7f0ca437052e8bd5a21" in raw
    assert "ALM_RUNNER_BRIDGE_NOT_READY" in raw


def test_alm_workflow_risk3_timeout_respects_gateway_contract() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    alm_block = raw.split("  alm-runner-bootstrap:", 1)[1]
    assert '"--timeout", "900",' in alm_block
    assert '"--timeout", "960",' not in alm_block

def test_authorized_gateway_maps_exact_command_to_existing_workflow_mode() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/reqsys run noteri-alm-runner-bootstrap'" in raw
    assert "'/reqsys run noteri-alm-runner-bootstrap')" in raw
    assert "target='noteri-desktop-watchdog-recovery.yml'" in raw
    assert "mode='alm-runner-bootstrap'" in raw
    assert "runner-recover|runner-bootstrap|runner-canary|reboot-once|alm-runner-bootstrap" in raw
