from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "configure_worker_pool_auth_restore_risk3.py"
spec = importlib.util.spec_from_file_location("worker_pool_auth_risk3", MODULE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "owner-risk3-exceptions.local.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "enabled": True,
                "owner_fingerprint": module.owner_fingerprint(),
                "actions": {},
                "development_mode": {"enabled": True, "expires_at": "2000-01-01T00:00:00+00:00"},
            }
        ),
        encoding="utf-8",
    )
    if os.name != "nt":
        os.chmod(path, 0o600)
    return path


def test_enable_adds_only_exact_action_and_preserves_expired_dev_mode(tmp_path: Path) -> None:
    path = _config(tmp_path)

    result = module.enable(path, 30)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert result["status"] == "enabled"
    assert list(data["actions"]) == [module.ACTION_ID]
    action = data["actions"][module.ACTION_ID]
    assert action["environment"] == "dev"
    assert action["scope"] == module.SCOPE
    assert action["command"] == module.COMMAND
    assert action["managed_by"] == module.MANAGED_BY
    assert data["development_mode"]["expires_at"].startswith("2000-01-01")


def test_disable_removes_only_managed_action(tmp_path: Path) -> None:
    path = _config(tmp_path)
    module.enable(path, 30)

    result = module.disable(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert result["removed"] is True
    assert module.ACTION_ID not in data["actions"]


def test_enable_fails_closed_on_conflicting_existing_action(tmp_path: Path) -> None:
    path = _config(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["actions"][module.ACTION_ID] = {
        "environment": "dev",
        "scope": module.SCOPE,
        "expires_at": "2099-01-01T00:00:00+00:00",
        "command": ["python", "other.py"],
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(module.ConfigError, match="risk3_action_conflict"):
        module.enable(path, 30)


def test_exact_command_avoids_sensitive_option_markers() -> None:
    joined = " ".join(module.COMMAND).lower()
    assert "token" not in joined
    assert "secret" not in joined
    assert "password" not in joined
    assert module.EVIDENCE_PATH.endswith("evidence.json")
