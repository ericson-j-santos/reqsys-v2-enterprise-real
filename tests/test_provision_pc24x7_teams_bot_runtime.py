from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import provision_pc24x7_teams_bot_runtime as provision


def _args(tmp_path: Path) -> argparse.Namespace:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    admin = tmp_path / "admin.yml"
    teams = tmp_path / "teams.yml"
    admin.write_text("services: {}\n", encoding="utf-8")
    teams.write_text("services: {}\n", encoding="utf-8")
    return argparse.Namespace(
        confirm=provision.CONFIRMATION,
        environment="dev",
        runtime_repo_root=runtime,
        expected_runtime_sha="a" * 40,
        vault_name="kv-test",
        expected_tenant_id="tenant-test",
        admin_override=admin,
        teams_override=teams,
        correlation_id="teams-bot-test",
        evidence_file=tmp_path / "evidence.json",
    )


def test_teams_bot_rejects_non_dev(tmp_path: Path) -> None:
    args = _args(tmp_path)
    args.environment = "prod"

    with pytest.raises(provision.ProvisionError, match="environment_must_be_dev"):
        provision.execute(args)


def test_teams_bot_rejects_wrong_confirmation(tmp_path: Path) -> None:
    args = _args(tmp_path)
    args.confirm = "WRONG"

    with pytest.raises(provision.ProvisionError, match="confirmation_required"):
        provision.execute(args)


def test_teams_bot_reuses_secret_without_exposing_it(monkeypatch, tmp_path: Path) -> None:
    args = _args(tmp_path)
    monkeypatch.setattr(provision, "_git_head", lambda _repo: args.expected_runtime_sha)
    monkeypatch.setattr(
        provision,
        "_load_existing_bot_secret",
        lambda _vault, _tenant: ("app-test", "super-secret-test-value"),
    )

    seen_secret_values: list[str | None] = []

    def fake_run(command, *, cwd=None, env=None, timeout=120, sensitive=False):
        seen_secret_values.append(None if env is None else env.get("TEAMS_BOT_SECRET"))
        if any("recreate_cofre_dev_pc24x7.py" in str(item) for item in command):
            return SimpleNamespace(stdout=json.dumps({"status": "passed"}), returncode=0)
        if any("pc24x7_teams_ephemeral_e2e.py" in str(item) for item in command):
            payload = {
                "status": "done",
                "token_revoked": True,
                "readiness": {"ready": True},
                "turn_idempotency_proven": True,
                "delivery_attempts": [{"teams_delivered": True, "teams_channel": "bot"}],
            }
            return SimpleNamespace(stdout=json.dumps(payload), returncode=0)
        raise AssertionError(command)

    monkeypatch.setattr(provision, "_run", fake_run)

    evidence = provision.execute(args)

    assert evidence["status"] == "passed"
    assert evidence["secret_value_exposed"] is False
    assert evidence["production_touched"] is False
    assert seen_secret_values[0] == "super-secret-test-value"
    assert seen_secret_values[1] == ""
    assert "super-secret-test-value" not in args.evidence_file.read_text(encoding="utf-8")


def test_compose_passes_teams_credentials_without_inline_secret_literal() -> None:
    override = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "pc24x7-teams-bot-runtime.override.yml"
    ).read_text(encoding="utf-8")

    assert "- TEAMS_BOT_APP_ID" in override
    assert "- TEAMS_BOT_APP_TENANT_ID" in override
    assert "- TEAMS_BOT_SECRET" in override
    assert "TEAMS_BOT_SECRET:" not in override
    assert "AI_CONVERSATION_OLLAMA_BASE_URL=http://host.docker.internal:11434" in override
