from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import reconcile_pc24x7_teams_dev_runtime as reconcile


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        confirm=reconcile.CONFIRMATION,
        environment="dev",
        expected_sha="a" * 40,
        vault_name="kv-dev",
        expected_tenant_id="tenant-dev",
        correlation_id="pc24x7-runtime-test",
        evidence_file=tmp_path / "evidence.json",
    )


def test_origin_accepts_only_expected_repository() -> None:
    assert reconcile._origin_is_expected(
        "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real.git"
    )
    assert reconcile._origin_is_expected(
        "git@github.com:ericson-j-santos/reqsys-v2-enterprise-real.git"
    )
    assert not reconcile._origin_is_expected(
        "https://github.com/ericson-j-santos/outro-repo.git"
    )
    assert not reconcile._origin_is_expected(
        "C:/cache/ericson-j-santos/reqsys-v2-enterprise-real.git"
    )


def test_sync_rejects_tracked_dirty_tree(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "runtime"
    repo.mkdir()

    def fake_git(_repo: Path, *args: str, check: bool = True):
        if args == ("remote", "get-url", "origin"):
            return SimpleNamespace(stdout="https://github.com/ericson-j-santos/reqsys-v2-enterprise-real.git\n", returncode=0)
        if args == ("status", "--porcelain", "--untracked-files=no"):
            return SimpleNamespace(stdout=" M backend/app/main.py\n", returncode=0)
        raise AssertionError(args)

    monkeypatch.setattr(reconcile, "_git", fake_git)

    with pytest.raises(reconcile.ReconcileError, match="runtime_tracked_tree_dirty"):
        reconcile._sync_runtime_repo(repo, "a" * 40)


def test_execute_reconciles_then_recreates_and_verifies(monkeypatch, tmp_path: Path) -> None:
    args = _args(tmp_path)
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    admin_override = tmp_path / "docker-compose.admin-dev.override.yml"
    admin_override.write_text("services: {}\n", encoding="utf-8")

    monkeypatch.setattr(reconcile, "_require_host", lambda: None)
    monkeypatch.setattr(
        reconcile,
        "_discover_runtime",
        lambda: (runtime_root, admin_override, reconcile.EXPECTED_PROJECT),
    )
    monkeypatch.setattr(
        reconcile,
        "_sync_runtime_repo",
        lambda _root, expected: {
            "before_sha": "b" * 40,
            "after_sha": expected,
            "origin_main_sha": expected,
            "fast_forward_performed": True,
        },
    )
    monkeypatch.setattr(
        reconcile,
        "_recreate_api",
        lambda *_args, **_kwargs: {
            "ok": True,
            "runtime_sha": args.expected_sha,
            "secret_value_observed": False,
            "production_touched": False,
        },
    )
    monkeypatch.setattr(
        reconcile,
        "_verify_runtime",
        lambda expected: {"build_sha": expected, "health_status": "healthy"},
    )

    evidence = reconcile.execute(args)

    assert evidence["status"] == "ready"
    assert evidence["sync"]["after_sha"] == args.expected_sha
    assert evidence["runtime"]["build_sha"] == args.expected_sha
    assert evidence["secret_value_exposed"] is False
    assert evidence["production_touched"] is False
    assert args.evidence_file.is_file()


def test_reconcile_is_dev_only(tmp_path: Path) -> None:
    args = _args(tmp_path)
    args.environment = "prod"

    with pytest.raises(reconcile.ReconcileError, match="environment_must_be_dev"):
        reconcile.execute(args)


def test_source_uses_fast_forward_and_never_hard_reset() -> None:
    text = Path("scripts/reconcile_pc24x7_teams_dev_runtime.py").read_text(encoding="utf-8")
    assert '"merge", "--ff-only", expected' in text
    assert "--untracked-files=no" in text
    assert 'reset", "--hard' not in text
