from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "restore_codex_worker_pool_token_dev.py"
WORKFLOW = ROOT / ".github" / "workflows" / "codex-worker-pool-smoke-dev.yml"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"

spec = importlib.util.spec_from_file_location("worker_pool_token_restore", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_restore_reuses_existing_token_without_rotation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("x" * 48, encoding="utf-8")
    monkeypatch.setattr(module, "_canonical_container_and_token_path", lambda: ("container-1", token_file))
    monkeypatch.setattr(module, "_validate_runtime", lambda _token: (200, True))
    seen: list[list[str]] = []
    monkeypatch.setattr(module, "_docker", lambda args: seen.append(args) or "")

    result = module.restore()

    assert result["token_rotated"] is False
    assert result["existing_token_reused"] is True
    assert result["service_restarted"] is False
    assert result["authenticated_readback"] is True
    assert seen == []


def test_restore_generates_token_locally_and_restarts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token_file = tmp_path / "token"
    monkeypatch.setattr(module, "_canonical_container_and_token_path", lambda: ("container-1", token_file))
    monkeypatch.setattr(module.secrets, "token_urlsafe", lambda _size: "y" * 64)
    monkeypatch.setattr(module, "_validate_runtime", lambda _token: (200, True))
    monkeypatch.setattr(module, "_wait_runtime", lambda _token: 200)
    seen: list[list[str]] = []
    monkeypatch.setattr(module, "_docker", lambda args: seen.append(args) or "")

    result = module.restore()

    assert token_file.read_text(encoding="utf-8").strip() == "y" * 64
    assert result["token_rotated"] is True
    assert result["service_restarted"] is True
    assert ["restart", "container-1"] in seen
    assert "y" * 64 not in json.dumps(result)


def test_restore_fails_closed_for_non_file_token_path(tmp_path: Path) -> None:
    with pytest.raises(module.RestoreError, match="worker_pool_token_path_not_file"):
        module._read_existing_token(tmp_path)


def test_workflow_uses_session_launcher_and_owner_risk3_gateway() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "chatgpt-operational-rules" in raw
    assert "session_launcher.py" in raw
    assert "SESSION_LAUNCH_OK" in raw
    assert "owner_risk3_gateway.py" in raw
    assert "reqsys.worker-pool-auth-file-restore.dev" in raw
    assert "repo://reqsys/environment/dev/worker-pool" in raw
    assert "scripts/restore_codex_worker_pool_token_dev.py" in raw
    assert "secrets." not in raw


def test_gateway_and_runner_policy_allow_only_fixed_restore_workflow() -> None:
    gateway = GATEWAY.read_text(encoding="utf-8")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert "github.event.comment.body == '/reqsys run codex-worker-pool-token-restore-dev'" in gateway
    assert "target='codex-worker-pool-token-restore-dev.yml'" in gateway
    assert "steps.route.outputs.target == 'codex-worker-pool-token-restore-dev.yml'" in gateway
    assert ".github/workflows/codex-worker-pool-smoke-dev.yml" in policy["approved_workflows"]
    assert ".github/workflows/codex-worker-pool-token-restore-dev.yml" not in policy["approved_workflows"]
    assert not (ROOT / ".github" / "workflows" / "codex-worker-pool-token-restore-dev.yml").exists()
