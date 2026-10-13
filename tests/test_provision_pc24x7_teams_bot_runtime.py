from __future__ import annotations

import argparse
from pathlib import Path

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
        runtime_profile="uncontracted-local",
        compose_project="teams-local-test",
        api_port="9210",
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


def test_unsupported_runtime_identity_blocks_before_secret(monkeypatch, tmp_path: Path) -> None:
    args = _args(tmp_path)
    args.runtime_profile = "uncontracted-local"
    args.compose_project = "uncontracted-project"
    args.api_port = "9210"
    touched = {"secret": False, "run": False}

    def forbidden_secret(*_args, **_kwargs):
        touched["secret"] = True
        raise AssertionError("secret must not be loaded")

    def forbidden_run(*_args, **_kwargs):
        touched["run"] = True
        raise AssertionError("command must not run")

    monkeypatch.setattr(provision, "_load_existing_bot_secret", forbidden_secret)
    monkeypatch.setattr(provision, "_run", forbidden_run)

    with pytest.raises(provision.ProvisionError, match="unsupported_runtime_identity"):
        provision.execute(args)

    assert touched == {"secret": False, "run": False}
    assert not args.evidence_file.exists()


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


def test_run_never_embeds_subprocess_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        provision.subprocess,
        "run",
        lambda *_args, **_kwargs: argparse.Namespace(
            returncode=9, stdout="SECRET_STDOUT", stderr="SECRET_STDERR"
        ),
    )
    with pytest.raises(provision.ProvisionError, match="^command_failed$") as captured:
        provision._run(["tool"], cwd=tmp_path)
    assert "SECRET" not in str(captured.value)
