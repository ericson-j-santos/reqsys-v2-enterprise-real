from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reconcile_pc24x7_public_dev_runtime.py"
OVERLAY = ROOT / "docker-compose.pc24x7-public-dev.yml"
NGINX = ROOT / "infra" / "nginx" / "default.pc24x7-public-dev.conf"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-study-mode-dev-reconcile.yml"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"


def _load():
    spec = importlib.util.spec_from_file_location("pc24x7_public_dev_reconcile", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_overlay_uses_production_frontend_build_and_same_sha() -> None:
    raw = OVERLAY.read_text(encoding="utf-8")
    assert "dockerfile: Dockerfile.prod" in raw
    assert "VITE_API_URL: /api" in raw
    assert "GITHUB_SHA: ${REQSYS_BUILD_SHA:?REQSYS_BUILD_SHA is required}" in raw
    assert "npm run dev" not in raw


def test_public_gateway_uses_static_frontend_and_blocks_vite_hmr() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    assert "proxy_pass http://frontend:80" in raw
    assert "frontend:5173" not in raw
    assert "location = /@vite/client" in raw
    assert "location ^~ /src/" in raw
    assert "return 404;" in raw
    assert "max-age=31536000, immutable" in raw


def test_public_gateway_defers_optional_runtime_core_dns_resolution() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    assert "resolver 127.0.0.11 valid=30s ipv6=off;" in raw
    assert "set $reqsys_runtime_upstream reqsys-runtime:8000;" in raw
    assert "proxy_pass http://reqsys-runtime:8000" not in raw
    assert "proxy_pass http://$reqsys_runtime_upstream/health;" in raw
    assert "proxy_pass http://$reqsys_runtime_upstream/api/runtime/build-info;" in raw
    assert "proxy_pass http://$reqsys_runtime_upstream/api/todo-events;" in raw
    assert "proxy_pass http://$reqsys_runtime_upstream/api/todo-events/;" in raw


def test_reconciler_is_dev_only_fast_forward_and_recreates_only_public_surface() -> None:
    module = _load()
    raw = SCRIPT.read_text(encoding="utf-8")
    assert module.EXPECTED_HOST == "DESKTOP-PDQK954"
    assert module.DEV_API_PORT == "8210"
    assert module.DEV_GATEWAY_PORT == "8083"
    assert '"merge", "--ff-only", expected' in raw
    assert 'reset", "--hard' not in raw
    assert '"--no-deps"' in raw
    assert '"api",' in raw and '"frontend",' in raw and '"nginx",' in raw
    assert "environment_must_be_dev" in raw
    assert "non_dev_runtime_target_blocked" in raw
    assert module.CLEAN_RUNTIME_DIRNAME == "wt-pc24x7-public-dev-governed"
    assert "worktree" in raw
    assert "dirty_runtime_checkout_preserved" in raw


def test_reconciler_requires_same_sha_static_frontend_and_negative_vite_control() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
    assert "/api/runtime/health" in raw
    assert "/api/runtime/readiness" in raw
    assert "/api/runtime/build-info" in raw
    assert "/task-console" in raw
    assert "/@vite/client" in raw
    assert 'vite["status"] == 404' in raw
    assert '"/assets/" in html' in raw
    assert '"/src/main.js" not in html' in raw
    assert "direct_sha == expected" in raw
    assert "gateway_sha == expected" in raw


def test_workflow_has_physical_then_independent_public_evidence() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "public-static" in raw
    assert "Reconcile full DEV runtime and static frontend" in raw
    assert "pc24x7_public_dev_tunnel.py --apply" in raw
    assert "pc24x7_dev_locator_publisher.py" in raw
    assert "needs: reconcile" in raw
    assert "Independent public same-SHA smoke" in raw
    assert "vite_hmr_exposed" in raw
    assert "production_touched" in raw
    assert "id-token: write" in raw
    assert "CCP_AZURE_CLIENT_ID: ${{ vars.CCP_AZURE_CLIENT_ID }}" in raw
    assert "CCP_AZURE_TENANT_ID: ${{ vars.CCP_AZURE_TENANT_ID }}" in raw
    assert "REQSYS_KEY_VAULT_NAME: ${{ vars.REQSYS_KEY_VAULT_NAME }}" in raw
    assert "azure/login@7184910d9eb2b1c5e48f7073824a90609bb9b6d6" in raw
    assert "actions/checkout@v4" not in raw
    assert "actions/setup-node@v4" not in raw
    assert "actions/upload-artifact@v4" not in raw
    assert '--vault-name "$env:REQSYS_KEY_VAULT_NAME"' in raw
    assert '--expected-tenant-id "$env:CCP_AZURE_TENANT_ID"' in raw


def test_workflow_limits_oidc_permission_to_reconcile_job() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    workflow_permissions = raw.split("\nconcurrency:", 1)[0].split("\npermissions:", 1)[1]
    reconcile = raw.split("\n  reconcile:", 1)[1].split("\n  public-smoke:", 1)[0]
    public_smoke = raw.split("\n  public-smoke:", 1)[1]

    assert "contents: read" in workflow_permissions
    assert "id-token:" not in workflow_permissions
    assert "permissions:\n      contents: read\n      id-token: write" in reconcile
    assert "permissions:\n      contents: read" in public_smoke
    assert "id-token:" not in public_smoke


def test_governed_worktree_is_created_without_cleaning_discovered_runtime(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = _load()
    discovered = tmp_path / "runtime-dirty"
    discovered.mkdir()
    expected = "a" * 40
    calls: list[tuple[str, ...]] = []

    def fake_git(_repo: Path, *args: str, check: bool = True):
        calls.append(args)
        if args == ("remote", "get-url", "origin"):
            return SimpleNamespace(
                stdout="https://github.com/ericson-j-santos/reqsys-v2-enterprise-real.git\n",
                returncode=0,
            )
        if args == ("fetch", "--prune", "origin", "main"):
            return SimpleNamespace(stdout="", returncode=0)
        if args == ("rev-parse", "origin/main"):
            return SimpleNamespace(stdout=expected + "\n", returncode=0)
        if args == ("merge-base", "--is-ancestor", expected, expected):
            return SimpleNamespace(stdout="", returncode=0)
        if args[:3] == ("worktree", "add", "--detach"):
            Path(args[3]).mkdir()
            return SimpleNamespace(stdout="", returncode=0)
        raise AssertionError(args)

    monkeypatch.setattr(module, "_git", fake_git)
    monkeypatch.setattr(
        module,
        "_sync_repo",
        lambda root, sha: {
            "before_sha": sha,
            "after_sha": sha,
            "origin_main_sha": sha,
            "fast_forward_performed": False,
        },
    )

    governed, evidence = module._prepare_governed_runtime_repo(discovered, expected)

    assert governed == tmp_path / module.CLEAN_RUNTIME_DIRNAME
    assert evidence["governed_worktree_created"] is True
    assert evidence["dirty_runtime_checkout_preserved"] is True
    assert not any(call[:2] == ("status", "--porcelain") for call in calls)


def test_compose_plan_uses_governed_sources_and_only_safe_local_overrides(
    tmp_path: Path,
) -> None:
    module = _load()
    governed = tmp_path / module.CLEAN_RUNTIME_DIRNAME
    admin = tmp_path / "local" / module.ADMIN_OVERRIDE_NAME
    pages = tmp_path / "local" / module.PAGES_OVERRIDE_NAME
    stale_teams = tmp_path / "old" / module.TEAMS_OVERRIDE
    stale_sha = tmp_path / "old" / ".tmp" / "cofre-runtime-sha.override.yml"
    for path in (
        governed / "docker-compose.yml",
        governed / "docker-compose.dev.yml",
        governed / module.TEAMS_OVERRIDE,
        governed / "docker-compose.pc24x7-cofre.yml",
        admin,
        pages,
        stale_teams,
        stale_sha,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("services: {}\n", encoding="utf-8")

    selected = module._select_compose_files(
        governed,
        [stale_teams, stale_sha, admin, pages],
    )

    assert governed / module.TEAMS_OVERRIDE in selected
    assert stale_teams not in selected
    assert stale_sha not in selected
    assert admin in selected
    assert pages in selected


def test_recreate_resolves_teams_secret_only_in_child_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = _load()
    governed = tmp_path / module.CLEAN_RUNTIME_DIRNAME
    (governed / module.OVERLAY).parent.mkdir(parents=True, exist_ok=True)
    (governed / module.OVERLAY).write_text("services: {}\n", encoding="utf-8")
    (governed / module.STATIC_NGINX).parent.mkdir(parents=True, exist_ok=True)
    (governed / module.STATIC_NGINX).write_text("server {}\n", encoding="utf-8")
    monkeypatch.setattr(
        module.provision,
        "_load_existing_bot_secret",
        lambda _vault, _tenant: ("app-placeholder", "secret-placeholder"),
    )
    monkeypatch.setattr(
        module,
        "_compose_base",
        lambda *_args, **_kwargs: ["docker", "compose"],
    )
    child_environments: list[dict[str, str]] = []

    def fake_run(_args, *, cwd, env=None, timeout=300, check=True, sensitive=False):
        child_environments.append(dict(env or {}))
        assert cwd == governed
        assert sensitive is True
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(module, "_run", fake_run)

    result = module._recreate_public_stack(
        governed,
        "wt-pc24x7-piloto",
        [],
        [],
        "a" * 40,
        "kv-placeholder",
        "tenant-placeholder",
    )

    assert len(child_environments) == 2
    assert all(env["TEAMS_BOT_SECRET"] == "secret-placeholder" for env in child_environments)
    assert all(env["TEAMS_BOT_APP_ID"] == "app-placeholder" for env in child_environments)
    assert result == {
        "credential_source": "azure_key_vault_existing",
        "credential_rotated": False,
        "secret_value_exposed": False,
    }


def test_sensitive_compose_failure_never_echoes_secret(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = _load()
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stderr="secret-placeholder must never reach evidence",
            stdout="",
        ),
    )

    with pytest.raises(module.ReconcileError) as caught:
        module._run(
            ["docker", "compose", "config", "--quiet"],
            cwd=tmp_path,
            sensitive=True,
        )

    assert "secret-placeholder" not in str(caught.value)
    assert "sensitive_command_failed" in str(caught.value)


def test_authorized_gateway_exposes_only_exact_static_reconcile_command() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/reqsys run pc24x7-public-dev-reconcile'" in raw
    assert "'/reqsys run pc24x7-public-dev-reconcile')" in raw
    assert "target='noteri-study-mode-dev-reconcile.yml'" in raw
    assert "mode='public-static'" in raw
    assert "-f mode=public-static" in raw
    assert "-f environment=prod" not in raw
