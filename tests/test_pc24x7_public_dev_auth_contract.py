from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.provision_pc24x7_teams_bot_runtime as provision
import scripts.reconcile_pc24x7_teams_dev_runtime as reconcile
import scripts.recreate_cofre_dev_pc24x7 as recreate


ROOT = Path(__file__).resolve().parents[1]


def test_public_overlay_is_last_and_sha_override_only_sets_github_sha(tmp_path: Path) -> None:
    public = tmp_path / "docker-compose.pc24x7-public-dev.yml"
    files = recreate.build_files(
        tmp_path,
        tmp_path / "admin.yml",
        tmp_path / "teams.yml",
        tmp_path / "sha.yml",
        public,
    )
    assert files[-1] == public
    source = (ROOT / "scripts" / "recreate_cofre_dev_pc24x7.py").read_text(encoding="utf-8")
    assert 'f\'      GITHUB_SHA: "{args.expected_sha}"\'' in source
    assert "ALLOW_DEMO_LOGIN" not in source.split("sha_override.write_text(", 1)[1].split("encoding=", 1)[0]


def test_rendered_public_contract_requires_strict_false() -> None:
    valid = json.dumps({"services": {"api": {"environment": {"ALLOW_DEMO_LOGIN": "false"}}}})
    assert recreate.validate_rendered_public_auth(valid) is False
    for value in ("true", "", "0"):
        payload = json.dumps({"services": {"api": {"environment": {"ALLOW_DEMO_LOGIN": value}}}})
        with pytest.raises(recreate.RecreateError, match="public_dev_demo_login_contract_invalid"):
            recreate.validate_rendered_public_auth(payload)


def test_base_and_local_opt_in_remain_available_while_public_is_false() -> None:
    base = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    local = (ROOT / "scripts" / "dev-local.sh").read_text(encoding="utf-8")
    public = (ROOT / "docker-compose.pc24x7-public-dev.yml").read_text(encoding="utf-8")
    assert "ALLOW_DEMO_LOGIN=${ALLOW_DEMO_LOGIN:-true}" in base
    assert 'ALLOW_DEMO_LOGIN="${ALLOW_DEMO_LOGIN:-true}"' in local
    assert 'ALLOW_DEMO_LOGIN: "false"' in public


def test_public_provision_is_rejected_before_key_vault_or_recreate(monkeypatch) -> None:
    touched = {"secret": False}

    def forbidden(*_args, **_kwargs):
        touched["secret"] = True
        raise AssertionError("secret load must not run")

    monkeypatch.setattr(provision, "_load_existing_bot_secret", forbidden)
    args = argparse.Namespace(
        confirm=provision.CONFIRMATION,
        environment="dev",
        runtime_profile=provision.PUBLIC_RUNTIME_PROFILE,
        compose_project=provision.PUBLIC_PROJECT,
        api_port=provision.PUBLIC_API_PORT,
    )
    with pytest.raises(provision.ProvisionError, match="public_runtime_demo_e2e_incompatible"):
        provision.execute(args)
    assert touched["secret"] is False


def test_absent_public_identity_blocks_before_sync(monkeypatch) -> None:
    args = argparse.Namespace(
        confirm=reconcile.CONFIRMATION,
        environment="dev",
        expected_sha="a" * 40,
    )
    monkeypatch.setattr(reconcile, "_require_host", lambda: None)
    monkeypatch.setattr(
        reconcile,
        "_discover_runtime",
        lambda: (_ for _ in ()).throw(reconcile.ReconcileError("public_dev_runtime_identity_not_proven")),
    )
    monkeypatch.setattr(
        reconcile,
        "_sync_runtime_repo",
        lambda *_args: (_ for _ in ()).throw(AssertionError("sync must not run")),
    )
    with pytest.raises(reconcile.ReconcileError, match="public_dev_runtime_identity_not_proven"):
        reconcile.execute(args)


def test_direct_auth_contract_requires_envelope_and_false(monkeypatch) -> None:
    calls = []

    def probe(path, timeout=20.0, *, require_envelope=False):
        calls.append((path, require_envelope))
        if path.endswith("build-info"):
            return {"build_sha": "a" * 40}
        if path.endswith("health"):
            return {"status": "healthy"}
        return {"demo_login_enabled": False}

    monkeypatch.setattr(reconcile, "_probe_json", probe)
    result = reconcile._verify_runtime("a" * 40)
    assert result["demo_login_enabled"] is False
    assert ("/v1/auth/config", True) in calls
    assert all("/api/v1/auth/config" not in path for path, _ in calls)


def test_direct_auth_true_never_completes(monkeypatch) -> None:
    sequence = {"/api/runtime/build-info": {"build_sha": "a" * 40}, "/api/runtime/health": {"status": "healthy"}, "/v1/auth/config": {"demo_login_enabled": True}}
    monkeypatch.setattr(reconcile, "_probe_json", lambda path, **_kwargs: sequence[path])
    ticks = iter([0.0, 100.0])
    monkeypatch.setattr(reconcile.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(reconcile.time, "sleep", lambda _seconds: None)
    with pytest.raises(reconcile.ReconcileError, match="runtime_same_sha_timeout"):
        reconcile._verify_runtime("a" * 40)


def test_remote_docker_and_unsafe_paths_are_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        recreate,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout='"tcp://remote:2375"'),
    )
    with pytest.raises(recreate.RecreateError, match="docker_remote_context_blocked"):
        recreate.validate_local_docker("container", cwd=tmp_path)
    with pytest.raises(recreate.RecreateError, match="public_dev_override_path_unsafe"):
        recreate.validate_public_override(tmp_path, Path(r"\\server\share\docker-compose.pc24x7-public-dev.yml"))


def test_recreate_uses_selected_inspection_and_sanitized_failure_contract() -> None:
    source = (ROOT / "scripts" / "recreate_cofre_dev_pc24x7.py").read_text(encoding="utf-8")
    assert "{{json .State}}" in source
    assert "{{json .Mounts}}" in source
    assert "{{json .Config.Env}}" not in source
    assert '"mutation_performed"' in source
    assert '"validation_failed_after_mutation"' in source
    assert "compose_config_contract_invalid" in source
