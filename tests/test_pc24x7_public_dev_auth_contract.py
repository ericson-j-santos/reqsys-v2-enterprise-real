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
    sha_block = source.split("sha_override.write_text(", 1)[1].split("encoding=", 1)[0]
    assert "GITHUB_SHA" in sha_block
    assert "ALLOW_DEMO_LOGIN" not in sha_block


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
    ticks = iter([0.0, 1.0, 100.0])
    monkeypatch.setattr(reconcile.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(reconcile.time, "sleep", lambda _seconds: None)
    with pytest.raises(reconcile.ReconcileError, match="runtime_same_sha_timeout"):
        reconcile._verify_runtime("a" * 40)


def test_remote_docker_and_unsafe_paths_are_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(recreate.os, "name", "nt")
    monkeypatch.setattr(recreate.socket, "gethostname", lambda: recreate.EXPECTED_HOST)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    monkeypatch.setattr(
        recreate,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout='"tcp://remote:2375"'),
    )
    with pytest.raises(recreate.RecreateError, match="docker_remote_context_blocked"):
        recreate.validate_local_docker(
            "container",
            cwd=tmp_path,
            public_override=tmp_path / recreate.PUBLIC_DEV_OVERRIDE_REL,
        )
    with pytest.raises(recreate.RecreateError, match="public_dev_override_path_unsafe"):
        recreate.validate_public_override(
            tmp_path,
            Path(r"\\server\share\docker-compose.pc24x7-public-dev.yml"),
            "a" * 40,
        )


def test_recreate_uses_selected_inspection_and_sanitized_failure_contract() -> None:
    source = (ROOT / "scripts" / "recreate_cofre_dev_pc24x7.py").read_text(encoding="utf-8")
    assert "{{json .State}}" not in source
    assert "{{json .Mounts}}" in source
    assert "{{json .Config.Env}}" not in source
    assert '"docker", "exec", container, "printenv", name' in source
    assert '"mutation_performed"' in source
    assert '"validation_failed_after_mutation"' in source
    assert "compose_config_contract_invalid" in source



def test_docker_environment_overrides_fail_before_inspection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(recreate.os, "name", "nt")
    monkeypatch.setattr(recreate.socket, "gethostname", lambda: recreate.EXPECTED_HOST)
    monkeypatch.setenv("DOCKER_HOST", "npipe:////./pipe/docker_engine")
    monkeypatch.setattr(
        recreate,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("docker must not run")),
    )
    with pytest.raises(recreate.RecreateError, match="docker_environment_override_blocked"):
        recreate.validate_local_docker(
            recreate.DEFAULT_CONTAINER,
            cwd=tmp_path,
            public_override=tmp_path / recreate.PUBLIC_DEV_OVERRIDE_REL,
        )


def test_auth_probe_disables_proxy_and_redirects(monkeypatch) -> None:
    seen = {}

    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self, _limit):
            return b'{"data":{"demo_login_enabled":false}}'

    class Opener:
        def open(self, request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            return Response()

    def build_opener(*handlers):
        seen["handlers"] = handlers
        return Opener()

    monkeypatch.setattr(recreate.urllib.request, "build_opener", build_opener)
    assert recreate.probe_auth_config() is False
    assert seen["url"].endswith("/v1/auth/config")
    assert any(isinstance(item, recreate.urllib.request.ProxyHandler) for item in seen["handlers"])


def test_public_path_rejects_traversal_before_metadata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        recreate,
        "_has_reparse_point",
        lambda _path: (_ for _ in ()).throw(AssertionError("lstat must not run")),
    )
    candidate = Path(str(tmp_path / "safe") + r"\..\docker-compose.pc24x7-public-dev.yml")
    with pytest.raises(recreate.RecreateError, match="public_dev_override_path_unsafe"):
        recreate.validate_public_override(tmp_path, candidate, "a" * 40)



def _execute_args(tmp_path: Path) -> argparse.Namespace:
    root = tmp_path / "repo"
    root.mkdir()
    for name in ("admin.yml", "teams.yml", "secret.txt", recreate.PUBLIC_DEV_OVERRIDE_REL.name):
        (root / name).write_text("services: {}\n", encoding="utf-8")
    return argparse.Namespace(
        expected_sha="a" * 40,
        runtime_profile=recreate.PUBLIC_RUNTIME_PROFILE,
        repo_root=root,
        public_dev_override=root / recreate.PUBLIC_DEV_OVERRIDE_REL,
        project=recreate.DEFAULT_PROJECT,
        container=recreate.DEFAULT_CONTAINER,
        secret_file=root / "secret.txt",
        admin_override=root / "admin.yml",
        teams_override=root / "teams.yml",
        health_timeout=1,
    )


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"RuntimeSha": "b" * 40}, "runtime_sha_mismatch"),
        ({"AllowDemoLogin": "true"}, "runtime_container_demo_login_not_false"),
        ({"Labels": {}}, "compose_project_mismatch"),
        ({"Mounts": []}, "secret_mount_not_read_only"),
    ],
)
def test_post_recreate_failures_preserve_mutation_state(
    monkeypatch, tmp_path: Path, change: dict, code: str
) -> None:
    args = _execute_args(tmp_path)
    root = args.repo_root
    backend = str((root / "backend").resolve())
    item = {
        "RuntimeSha": args.expected_sha,
        "AllowDemoLogin": "false",
        "Labels": {
            "com.docker.compose.project": args.project,
            "com.docker.compose.service": "api",
        },
        "Mounts": [
            {"Destination": "/run/secrets/cofre_keyring_passphrase", "RW": False},
            {"Destination": "/data", "Type": "volume", "RW": True},
            {"Destination": "/app", "Source": backend},
        ],
    }
    item.update(change)
    monkeypatch.setattr(recreate, "git_head", lambda _root: args.expected_sha)
    monkeypatch.setattr(
        recreate, "validate_public_override", lambda *_args: args.public_dev_override
    )
    monkeypatch.setattr(recreate, "validate_local_docker", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        recreate,
        "run",
        lambda command, **_kwargs: SimpleNamespace(
            stdout=(
                '{"services":{"api":{"environment":{"ALLOW_DEMO_LOGIN":"false"}}}}'
                if "config" in command
                else ""
            ),
            returncode=0,
        ),
    )
    monkeypatch.setattr(recreate, "wait_healthy", lambda *_args, **_kwargs: "healthy")
    monkeypatch.setattr(recreate, "inspect_container", lambda *_args, **_kwargs: item)
    monkeypatch.setattr(recreate, "probe_auth_config", lambda: False)

    with pytest.raises(recreate.RecreateError, match=code) as captured:
        recreate.execute(args)

    assert captured.value.mutation_state == "attempted_unverified"
    assert captured.value.mutation_performed is True


def test_compose_up_timeout_is_mutation_unknown(monkeypatch, tmp_path: Path) -> None:
    args = _execute_args(tmp_path)
    monkeypatch.setattr(recreate, "git_head", lambda _root: args.expected_sha)
    monkeypatch.setattr(
        recreate, "validate_public_override", lambda *_args: args.public_dev_override
    )
    monkeypatch.setattr(recreate, "validate_local_docker", lambda *_args, **_kwargs: None)

    def fake_run(command, **_kwargs):
        if "config" in command:
            return SimpleNamespace(
                stdout='{"services":{"api":{"environment":{"ALLOW_DEMO_LOGIN":"false"}}}}',
                returncode=0,
            )
        raise recreate.RecreateError("command_timeout")

    monkeypatch.setattr(recreate, "run", fake_run)
    with pytest.raises(recreate.RecreateError, match="command_timeout") as captured:
        recreate.execute(args)
    assert captured.value.mutation_state == "attempted_unknown"


def test_reparse_ancestor_is_checked_before_resolve(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    overlay = root / recreate.PUBLIC_DEV_OVERRIDE_REL
    checked = []

    monkeypatch.setattr(Path, "exists", lambda _self: True)
    monkeypatch.setattr(
        recreate,
        "_has_reparse_point",
        lambda path: checked.append(path) or path == root.parent,
    )
    with pytest.raises(recreate.RecreateError, match="public_dev_override_reparse_blocked"):
        recreate._lexical_public_override(root, overlay)
    assert root.parent in checked
