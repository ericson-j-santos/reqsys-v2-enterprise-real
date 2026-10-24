from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "reconcile_pc24x7_teams_dev_runtime.py"
SPEC = importlib.util.spec_from_file_location("reconcile_pc24x7_teams_dev_runtime", MODULE_PATH)
assert SPEC and SPEC.loader
reconcile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconcile)


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


def test_public_override_hash_uses_git_path_filters(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "runtime"
    repo.mkdir()
    public = repo / reconcile.PUBLIC_OVERRIDE_NAME
    public.write_bytes(b"services:\r\n  api: {}\r\n")
    blob = "1" * 40
    observed_calls: list[tuple[str, ...]] = []

    def fake_git(_repo: Path, *args: str, check: bool = True):
        observed_calls.append(args)
        if args == (
            "rev-parse",
            f"{'a' * 40}:{reconcile.PUBLIC_OVERRIDE_NAME}",
        ):
            return SimpleNamespace(stdout=f"{blob}\n", returncode=0)
        if args == (
            "hash-object",
            "--path",
            reconcile.PUBLIC_OVERRIDE_NAME,
            str(public),
        ):
            return SimpleNamespace(stdout=f"{blob}\n", returncode=0)
        raise AssertionError(args)

    monkeypatch.setattr(reconcile, "_git", fake_git)

    assert reconcile._validate_public_override(repo, public, "a" * 40) == public.resolve()
    assert not any("--no-filters" in args for args in observed_calls)


def test_execute_reconciles_then_recreates_and_verifies(monkeypatch, tmp_path: Path) -> None:
    args = _args(tmp_path)
    monkeypatch.setenv("REQSYS_DEV_RUNNER_INSTANCE_ID", "reqsys-pc-test01")
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    admin_override = tmp_path / "docker-compose.admin-dev.override.yml"
    admin_override.write_text("services: {}\n", encoding="utf-8")
    public_override = runtime_root / reconcile.PUBLIC_OVERRIDE_NAME
    public_override.write_text("services: {}\n", encoding="utf-8")
    sequence: list[str] = []
    recreate_args: list[object] = []

    monkeypatch.setattr(reconcile, "_require_host", lambda: sequence.append("host"))
    monkeypatch.setattr(
        reconcile,
        "_discover_runtime",
        lambda: (
            sequence.append("discover")
            or (runtime_root, admin_override, public_override, reconcile.EXPECTED_PROJECT)
        ),
    )
    monkeypatch.setattr(
        reconcile,
        "_sync_runtime_repo",
        lambda _root, expected: sequence.append("sync") or {
            "before_sha": "b" * 40,
            "after_sha": expected,
            "origin_main_sha": expected,
            "fast_forward_performed": True,
        },
    )
    monkeypatch.setattr(
        reconcile,
        "_validate_public_override",
        lambda _root, candidate, expected: (
            sequence.append("overlay_after_sync") or candidate
        ),
    )

    def fake_recreate(*call_args, **_kwargs):
        sequence.append("recreate")
        recreate_args.extend(call_args)
        return {
            "ok": True,
            "runtime_sha": args.expected_sha,
            "secret_value_observed": False,
            "production_touched": False,
        }

    monkeypatch.setattr(reconcile, "_recreate_api", fake_recreate)
    monkeypatch.setattr(
        reconcile,
        "_verify_runtime",
        lambda expected: sequence.append("verify") or {
            "build_sha": expected,
            "health_status": "healthy",
            "demo_login_enabled": False,
            "auth_contract_consistent": True,
        },
    )

    evidence = reconcile.execute(args)

    assert evidence["status"] == "ready"
    assert sequence == ["host", "discover", "sync", "overlay_after_sync", "recreate", "verify"]
    assert recreate_args[2] == public_override
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


def test_docker_environment_override_blocks_before_commands(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DOCKER_CONTEXT", "remote")
    monkeypatch.setattr(
        reconcile,
        "_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("docker must not run")),
    )
    with pytest.raises(reconcile.ReconcileError, match="docker_environment_override_blocked"):
        reconcile._require_local_docker(tmp_path)


def _discovery_fixture(monkeypatch, tmp_path: Path, *, nginx_has_public: bool = True):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    admin = tmp_path / reconcile.ADMIN_OVERRIDE_NAME
    admin.write_text("services: {}\n", encoding="utf-8")
    public = runtime / reconcile.PUBLIC_OVERRIDE_NAME
    public.write_text("services: {}\n", encoding="utf-8")
    base = runtime / "docker-compose.yml"
    base.write_text("services: {}\n", encoding="utf-8")

    api_files = f"{base},{admin},{runtime / '.tmp' / 'cofre-runtime-sha.override.yml'}"
    sibling_files = f"{base},{admin},{public}"
    labels = {
        "api-id": {
            "com.docker.compose.project": reconcile.EXPECTED_PROJECT,
            "com.docker.compose.service": "api",
            "com.docker.compose.project.working_dir": str(runtime),
            "com.docker.compose.project.config_files": api_files,
        },
        "frontend-id": {
            "com.docker.compose.project": reconcile.EXPECTED_PROJECT,
            "com.docker.compose.service": "frontend",
            "com.docker.compose.project.working_dir": str(runtime),
            "com.docker.compose.project.config_files": sibling_files,
        },
        "nginx-id": {
            "com.docker.compose.project": reconcile.EXPECTED_PROJECT,
            "com.docker.compose.service": "nginx",
            "com.docker.compose.project.working_dir": str(runtime),
            "com.docker.compose.project.config_files": (
                sibling_files if nginx_has_public else f"{base},{admin}"
            ),
        },
    }

    def fake_run(args, **_kwargs):
        if args[1] == "ps":
            service_filter = next(
                value for value in args if str(value).startswith("label=com.docker.compose.service=")
            )
            service = service_filter.rsplit("=", 1)[-1]
            return SimpleNamespace(stdout=f"{service}-id\n", returncode=0)
        if args[1] == "port":
            return SimpleNamespace(
                stdout="8000/tcp -> 0.0.0.0:8210\n8000/tcp -> [::]:8210\n",
                returncode=0,
            )
        raise AssertionError(args)

    def fake_inspect(container_id, template, _cwd):
        name = template.split('"')[1]
        return labels[container_id][name]

    monkeypatch.setattr(reconcile, "_require_local_docker", lambda _cwd: None)
    monkeypatch.setattr(reconcile, "_tool", lambda name: name)
    monkeypatch.setattr(reconcile, "_run", fake_run)
    monkeypatch.setattr(reconcile, "_inspect_value", fake_inspect)
    monkeypatch.setattr(
        reconcile,
        "_validate_public_override",
        lambda _root, candidate, *_args: candidate.resolve(),
    )
    return runtime, admin, public


def test_discovery_recovers_api_only_public_overlay_drift_from_two_siblings(
    monkeypatch, tmp_path: Path
) -> None:
    runtime, admin, public = _discovery_fixture(monkeypatch, tmp_path)

    observed = reconcile._discover_runtime()

    assert observed == (
        runtime.resolve(),
        admin.resolve(),
        public.resolve(),
        reconcile.EXPECTED_PROJECT,
    )


def test_discovery_refuses_api_drift_without_both_sibling_proofs(
    monkeypatch, tmp_path: Path
) -> None:
    _discovery_fixture(monkeypatch, tmp_path, nginx_has_public=False)

    with pytest.raises(
        reconcile.ReconcileError, match="public_dev_runtime_identity_not_proven"
    ):
        reconcile._discover_runtime()



def test_recreate_invalid_json_preserves_unknown_mutation(monkeypatch, tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    teams = runtime / reconcile.TEAMS_OVERRIDE_REL
    teams.parent.mkdir(parents=True)
    teams.write_text("services: {}\n", encoding="utf-8")
    public = runtime / reconcile.PUBLIC_OVERRIDE_NAME
    public.write_text("services: {}\n", encoding="utf-8")
    admin = runtime / reconcile.ADMIN_OVERRIDE_NAME
    admin.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(
        reconcile.provision,
        "_load_existing_bot_secret",
        lambda *_args: ("app-id", "secret-value"),
    )
    monkeypatch.setattr(
        reconcile,
        "_run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="not-json", stderr=""
        ),
    )
    with pytest.raises(reconcile.ReconcileError, match="recreate_json_invalid") as captured:
        reconcile._recreate_api(
            runtime, admin, public, "a" * 40, "vault", "tenant"
        )
    assert captured.value.mutation_state == "attempted_unknown"


def test_verify_failure_after_recreate_preserves_unverified_state(
    monkeypatch, tmp_path: Path
) -> None:
    args = _args(tmp_path)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    admin = runtime / reconcile.ADMIN_OVERRIDE_NAME
    public = runtime / reconcile.PUBLIC_OVERRIDE_NAME
    admin.write_text("services: {}\n", encoding="utf-8")
    public.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(reconcile, "_require_host", lambda: None)
    monkeypatch.setattr(
        reconcile,
        "_discover_runtime",
        lambda: (runtime, admin, public, reconcile.EXPECTED_PROJECT),
    )
    monkeypatch.setattr(
        reconcile,
        "_sync_runtime_repo",
        lambda *_args: {
            "before_sha": args.expected_sha,
            "after_sha": args.expected_sha,
            "origin_main_sha": args.expected_sha,
            "fast_forward_performed": False,
        },
    )
    monkeypatch.setattr(
        reconcile, "_validate_public_override", lambda *_args: public
    )
    monkeypatch.setattr(
        reconcile,
        "_recreate_api",
        lambda *_args: {"mutation_state": "verified"},
    )
    monkeypatch.setattr(
        reconcile,
        "_verify_runtime",
        lambda *_args: (_ for _ in ()).throw(
            reconcile.ReconcileError("runtime_same_sha_timeout")
        ),
    )
    with pytest.raises(reconcile.ReconcileError, match="runtime_same_sha_timeout") as captured:
        reconcile.execute(args)
    assert captured.value.mutation_state == "attempted_unverified"


def test_run_never_embeds_subprocess_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        reconcile.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=7, stdout="SECRET_STDOUT", stderr="SECRET_STDERR"
        ),
    )
    with pytest.raises(reconcile.ReconcileError, match="^command_failed$") as captured:
        reconcile._run(["tool"], cwd=tmp_path)
    assert "SECRET" not in str(captured.value)

