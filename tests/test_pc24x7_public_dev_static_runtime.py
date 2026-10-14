from __future__ import annotations
import sys

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

import subprocess
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


def test_public_gateway_preserves_runtime_todo_subpath_and_query() -> None:
    raw = NGINX.read_text(encoding="utf-8")
    assert "location ^~ /runtime-core/api/todo-events/" in raw
    # A rewrite replacement without '?' retains the original query string.
    assert "rewrite ^/runtime-core(/api/todo-events/.*)$ $1 break;" in raw
    assert "proxy_pass http://$reqsys_runtime_upstream;" in raw
    assert "proxy_pass http://$reqsys_runtime_upstream/api/todo-events/;" not in raw


def test_reconciler_is_dev_only_fast_forward_and_recreates_only_public_surface() -> None:
    module = _load()
    raw = SCRIPT.read_text(encoding="utf-8")
    assert module.EXPECTED_HOST == "DESKTOP-PDQK954"
    assert module.DEV_API_PORT == "8210"
    assert module.DEV_GATEWAY_PORT == "8083"
    assert '"merge", "--ff-only", expected' in raw
    assert 'reset", "--hard' not in raw
    assert '"--no-deps"' in raw
    assert '"api",' in raw and '"frontend",' in raw
    assert (
        'base + ["up", "-d", "--no-deps", "--force-recreate", "nginx"]'
        in raw
    )
    assert "_wait_for_api_ready(expected_sha)" in raw
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
    assert "azure/login@a641126d1b8aa4d1fa005f4f92df94a3a4c4c906" in raw
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
    events: list[str] = []

    def fake_run(args, *, cwd, env=None, timeout=300, check=True, sensitive=False, stage=None):
        child_environments.append(dict(env or {}))
        events.append(" ".join(args))
        assert cwd == governed
        assert sensitive is True
        assert stage in {"compose_config", "api_frontend_up", "nginx_up"}
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(
        module,
        "_wait_for_api_ready",
        lambda _sha: events.append("api-ready")
        or {
            "strategy": "api_frontend_then_nginx",
            "attempts": 2,
            "build_sha": "a" * 40,
            "health": "ok",
        },
    )

    result = module._recreate_public_stack(
        governed,
        "wt-pc24x7-piloto",
        [],
        [],
        "a" * 40,
        "kv-placeholder",
        "tenant-placeholder",
    )

    assert len(child_environments) == 3
    assert all(env["TEAMS_BOT_SECRET"] == "secret-placeholder" for env in child_environments)
    assert all(env["TEAMS_BOT_APP_ID"] == "app-placeholder" for env in child_environments)
    assert events[1].endswith("up -d --build --no-deps api frontend")
    assert events[2] == "api-ready"
    assert events[3].endswith("up -d --no-deps --force-recreate nginx")
    assert result == {
        "credential_source": "azure_key_vault_existing",
        "credential_rotated": False,
        "secret_value_exposed": False,
        "api_startup": {
            "strategy": "api_frontend_then_nginx",
            "attempts": 2,
            "build_sha": "a" * 40,
            "health": "ok",
        },
    }


def test_wait_for_api_ready_retries_until_same_sha_is_healthy(monkeypatch) -> None:
    module = _load()
    expected = "a" * 40
    calls: list[str] = []

    def fake_probe(url: str):
        calls.append(url)
        if len(calls) == 1:
            raise module.ReconcileError("probe_failed:ConnectionRefusedError")
        if url.endswith("/api/runtime/build-info"):
            return {
                "status": 200,
                "body": '{"data":{"build_sha":"' + expected + '"}}',
            }
        return {"status": 200, "body": '{"data":{"status":"ok"}}'}

    monkeypatch.setattr(module, "_probe", fake_probe)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    result = module._wait_for_api_ready(expected, timeout_seconds=1, poll_seconds=0)

    assert result == {
        "strategy": "api_frontend_then_nginx",
        "attempts": 2,
        "build_sha": expected,
        "health": "ok",
    }
    assert calls == [
        f"http://127.0.0.1:{module.DEV_API_PORT}/api/runtime/build-info",
        f"http://127.0.0.1:{module.DEV_API_PORT}/api/runtime/build-info",
        f"http://127.0.0.1:{module.DEV_API_PORT}/api/runtime/health",
    ]


def test_wait_for_api_ready_fails_closed_when_sha_never_matches(monkeypatch) -> None:
    module = _load()
    clock = [0.0]

    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        module.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    monkeypatch.setattr(
        module,
        "_probe",
        lambda url: {
            "status": 200,
            "body": (
                '{"data":{"build_sha":"' + "b" * 40 + '"}}'
                if url.endswith("/api/runtime/build-info")
                else '{"data":{"status":"ok"}}'
            ),
        },
    )

    with pytest.raises(module.ReconcileError, match="api_startup_timeout") as caught:
        module._wait_for_api_ready("a" * 40, timeout_seconds=2, poll_seconds=1)

    assert "b" * 40 in str(caught.value)


def test_failure_evidence_preserves_only_sanitized_reconcile_details() -> None:
    module = _load()

    assert module._safe_failure_detail(
        module.ReconcileError("api_startup_timeout:direct_api_probe_failed")
    ) == "api_startup_timeout:direct_api_probe_failed"
    assert module._safe_failure_detail(
        RuntimeError("external exception could contain a secret")
    ) == "reconciliation_failed"


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


def test_reconciler_loads_maintenance_as_sibling_for_direct_script_execution() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
    assert "def _load_sibling_module(filename: str, module_name: str)" in raw
    assert '"self_hosted_dev_maintenance.py"' in raw
    assert "except (ImportError, ModuleNotFoundError):" in raw
    assert '"self_hosted_dev_maintenance.py"' in raw


def test_reconciler_direct_help_runs_without_scripts_package_import_error() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--expected-sha" in completed.stdout


@pytest.mark.parametrize("stage", ["compose_config", "api_frontend_up", "nginx_up"])
def test_sensitive_failure_identifies_only_allowlisted_stage(monkeypatch, tmp_path, stage):
    module = _load()
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=1, stderr="SECRET=never-publish", stdout="private-output"
    ))
    with pytest.raises(module.ReconcileError) as caught:
        module._run(["docker", "compose"], cwd=tmp_path, sensitive=True, stage=stage)
    assert str(caught.value) == f"sensitive_command_failed:{stage}:docker:exit_1"


def test_stage_rejects_arbitrary_text_before_running_command(monkeypatch, tmp_path):
    module = _load()
    def forbidden(*args, **kwargs):
        raise AssertionError("subprocess must not execute")
    monkeypatch.setattr(module.subprocess, "run", forbidden)
    with pytest.raises(module.ReconcileError, match="command_stage_not_allowed"):
        module._run(["docker"], cwd=tmp_path, sensitive=True, stage="SECRET=private")


def test_study_mode_direct_help_handles_namespace_import_error():
    script = ROOT / "scripts" / "noteri_study_mode_dev_reconcile.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"], cwd=ROOT,
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--expected-sha" in completed.stdout


@pytest.mark.parametrize("failure", [OSError("SECRET=private"), subprocess.TimeoutExpired(["secret-command"], 1, output="SECRET")])
def test_sensitive_spawn_and_timeout_preserve_stage_without_details(monkeypatch, tmp_path, failure):
    module = _load()
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(module.subprocess, "run", fail)
    with pytest.raises(module.ReconcileError) as caught:
        module._run(["docker"], cwd=tmp_path, sensitive=True, stage="compose_config")
    assert "compose_config" in str(caught.value)
    assert "SECRET" not in str(caught.value)
    assert "secret-command" not in str(caught.value)


def test_study_mode_loader_falls_back_on_explicit_import_error(monkeypatch):
    import builtins
    import runpy
    original_import = builtins.__import__
    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "scripts" and "self_hosted_dev_maintenance" in fromlist:
            raise ImportError("cannot import name self_hosted_dev_maintenance")
        return original_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    monkeypatch.setattr(sys, "argv", ["noteri_study_mode_dev_reconcile.py", "--help"])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(ROOT / "scripts/noteri_study_mode_dev_reconcile.py"), run_name="__main__")
    assert caught.value.code == 0



def test_legacy_public_static_reconcile_blocks_before_any_runtime_mutation(
    monkeypatch, tmp_path: Path,
) -> None:
    module = _load()
    monkeypatch.setattr(
        module.portable_dev, "verify_if_active", lambda _sha: None,
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("live runtime must remain untouched")

    monkeypatch.setattr(module, "_discover_runtime", forbidden)
    monkeypatch.setattr(module, "_prepare_governed_runtime_repo", forbidden)
    monkeypatch.setattr(module, "_recreate_public_stack", forbidden)
    monkeypatch.setattr(module, "_verify", forbidden)
    args = SimpleNamespace(
        confirm=module.CONFIRMATION, environment="dev",
        expected_sha="a" * 40, vault_name="kv-placeholder",
        expected_tenant_id="tenant-placeholder",
        correlation_id="reqsys2546-prevent-unsafe-dev-cutover",
        evidence_file=tmp_path / "evidence.json",
    )
    with pytest.raises(
        module.ReconcileError,
        match="^legacy_dev_backup_and_rollback_not_verified$",
    ):
        module.execute(args)
    assert not args.evidence_file.exists()


def test_existing_verified_portable_dev_remains_read_only(
    monkeypatch, tmp_path: Path,
) -> None:
    module = _load()
    monkeypatch.setattr(
        module.portable_dev, "verify_if_active",
        lambda _sha: {"local_runtime_contract_ready": True},
    )
    monkeypatch.setattr(
        module, "_discover_runtime",
        lambda: pytest.fail("legacy Docker must not be discovered"),
    )
    args = SimpleNamespace(
        confirm=module.CONFIRMATION, environment="dev",
        expected_sha="a" * 40, correlation_id="reqsys2546-portable-readonly",
        evidence_file=tmp_path / "evidence.json",
    )
    observed = module.execute(args)
    assert observed["legacy_reconciliation_deferred"] is True
    assert observed["credentials_reused"] is False
    assert observed["local_runtime_contract_ready"] is True
    assert args.evidence_file.exists()
    assert __import__("json").loads(
        args.evidence_file.read_text(encoding="utf-8")
    ) == observed


def test_public_static_workflow_fails_closed_before_oidc_or_deploy() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    guard = raw.index(
        "Quarantine legacy public-static without governed backup and rollback"
    )
    azure = raw.index("Login Azure by OIDC for DEV credential reuse")
    deploy = raw.index("Reconcile full DEV runtime and static frontend")
    locator = raw.index("Reconcile public tunnels and publish signed locator")
    assert guard < azure < deploy < locator
    before = raw[guard:raw.index("- name: Validate public static reconciler syntax")]
    assert "inputs.mode == 'public-static'" in before
    assert (
        "throw 'PUBLIC_STATIC_REQUIRES_GOVERNED_SESSION_BACKUP_AND_ROLLBACK'"
        in before
    )


def _public_dev_governed_inventory_guard_active(raw: str) -> bool:
    """Prevent any public-static mutator running before governed inventory."""
    rules = raw.find("      - name: Checkout immutable rules for governed Desktop session")
    session = raw.find("      - name: Bootstrap isolated and governed Desktop session")
    inventory = raw.find("      - name: Inventory public DEV through governed Gateway (read-only)")
    blockade = raw.find("      - name: Quarantine legacy public-static without governed backup and rollback")
    azure = raw.find("      - name: Login Azure by OIDC for DEV credential reuse")
    deploy = raw.find("      - name: Reconcile full DEV runtime and static frontend")
    locator = raw.find("      - name: Reconcile public tunnels and publish signed locator")
    if not (0 <= rules < session < inventory < blockade < azure < deploy < locator):
        return False
    rules_step = raw[rules:session]
    session_step = raw[session:inventory]
    inventory_step = raw[inventory:blockade]
    guard_step = raw[blockade:azure]
    return all((
        "if: github.event_name == 'workflow_dispatch'" in rules_step,
        "if: github.event_name == 'workflow_dispatch'" in session_step,
        "session_launcher.py" in session_step,
        "--require-runner-version-preflight" in session_step,
        "'--expected-head', '${{ github.sha }}'" in inventory_step,
        "'--risk', '1'" in inventory_step,
        "'--stdout-only'" in inventory_step,
        "'--', $env:GATEWAY_PYTHON, '-B', $probe" in inventory_step,
        "state_changed -ne $false" in inventory_step,
        "session_id -ne $env:SESSION_ID" in inventory_step,
        "inventory_collected = $true" in inventory_step,
        "backup_verified = $false" in inventory_step,
        "rollback_rehearsal_verified = $false" in inventory_step,
        "if: github.event_name == 'workflow_dispatch' && inputs.mode == 'public-static'" in guard_step,
        "throw 'PUBLIC_STATIC_REQUIRES_GOVERNED_SESSION_BACKUP_AND_ROLLBACK'" in guard_step,
        "always()" not in guard_step,
    ))


def test_public_dev_release_collects_only_governed_inventory_before_quarantine():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert _public_dev_governed_inventory_guard_active(raw)
    inventory = raw.index("Inventory public DEV through governed Gateway (read-only)")
    blockade = raw.index("Quarantine legacy public-static")
    assert inventory < blockade < raw.index("Login Azure by OIDC")
    assert blockade < raw.index("Reconcile full DEV runtime")
    assert blockade < raw.index("pc24x7_public_dev_tunnel.py --apply")


def test_public_dev_governed_inventory_security_control_detects_bypass():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert _public_dev_governed_inventory_guard_active(raw)
    without_quarantine = raw.replace(
        "throw 'PUBLIC_STATIC_REQUIRES_GOVERNED_SESSION_BACKUP_AND_ROLLBACK'",
        "Write-Host 'unsafe bypass'",
        1,
    )
    assert not _public_dev_governed_inventory_guard_active(without_quarantine)
    without_gateway = raw.replace("'--risk', '1'", "'--risk', '2'", 1)
    assert not _public_dev_governed_inventory_guard_active(without_gateway)
    without_session = raw.replace(
        "if: github.event_name == 'workflow_dispatch'\n        id: session",
        "if: github.event_name == 'workflow_dispatch' && inputs.mode == 'study-mode'\n        id: session",
        1,
    )
    assert not _public_dev_governed_inventory_guard_active(without_session)


def test_public_dev_read_only_receipt_never_claims_backup_or_deploy():
    raw = WORKFLOW.read_text(encoding="utf-8")
    start = raw.index("      - name: Inventory public DEV through governed Gateway (read-only)")
    end = raw.index("      - name: Quarantine legacy public-static")
    step = raw[start:end]
    for value in (
        "status = 'preflight_only'",
        "runtime_sha_verified = $false",
        "database_result = 'unverified'",
        "backup_verified = $false",
        "rollback_rehearsal_verified = $false",
        "deployment_performed = $false",
        "runtime_mutated = $false",
        "production_touched = $false",
    ):
        assert value in step
    assert "New-Item -ItemType Directory" in step
    assert "TEAMS_BOT_SECRET" not in step
