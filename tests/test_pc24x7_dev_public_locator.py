import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "public-dev-locator" / "index.html"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-reqsys-pages-composite.yml"
SUPERVISOR = ROOT / "scripts" / "pc24x7_dev_runtime_supervisor.py"
INSTALLER = ROOT / "scripts" / "pc24x7_dev_runtime_supervisor_install.py"
MANIFEST = ROOT / "infra" / "public-access-urls.json"
PUBLISHER = ROOT / "scripts" / "pc24x7_dev_locator_publisher.py"
RESOLVER = ROOT / "scripts" / "resolve_pc24x7_dev_locator.mjs"
PROMOTION = ROOT / ".github" / "workflows" / "fly-automatic-environment-promotion.yml"


def test_locator_requires_valid_signed_fresh_cloudflare_state():
    raw = HTML.read_text(encoding="utf-8")
    assert "Ed25519" in raw
    assert "expires_at" in raw
    assert "environment!==\"dev\"" in raw
    assert '.endsWith(".trycloudflare.com")' in raw
    assert "signature_b64" in raw
    assert "reqsys-dev-locator-" in raw
    assert "PRIVATE" not in raw.upper()


def test_locator_preserves_only_relative_target_route():
    raw = HTML.read_text(encoding="utf-8")
    assert 'requestedTarget=params.get("target")||"/task-console"' in raw
    assert 'requestedTarget.startsWith("/")' in raw
    assert '!requestedTarget.startsWith("//")' in raw
    assert 'payload.selected_url+target' in raw


def test_pages_composite_publishes_stable_dev_path():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "cp -a docs/public-dev-locator/. site/dev/" in raw
    assert "test -s site/dev/index.html" in raw
    assert "actions/deploy-pages@v4" in raw


def test_supervisor_uses_cloudflare_and_signed_locator_only():
    raw = SUPERVISOR.read_text(encoding="utf-8").lower()
    assert "pc24x7_public_dev_tunnel.py" in raw
    assert "pc24x7_dev_locator_publisher.py" in raw
    assert "zero_additional_cost" in raw
    assert "tailscale_funnel" not in raw
    assert "pc24x7_nport_tunnel.py" not in raw


def test_installer_preserves_resilient_task_settings():
    raw = INSTALLER.read_text(encoding="utf-8")
    assert '"pc24x7_dev_locator_publisher.py"' in raw
    assert "DisallowStartIfOnBatteries = False" in raw
    assert "StopIfGoingOnBatteries = False" in raw
    assert "StartWhenAvailable = True" in raw
    assert 'ExecutionTimeLimit = "PT10M"' in raw


def test_public_manifest_uses_pages_as_stable_dev_entrypoint():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    dev = manifest["runtime_discovery"]["dev"]
    assert dev["stable_url_target"] == "https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/"
    assert dev["cost_policy"] == "zero_additional_cost"
    assert dev["locator_channel"] == "ntfy_signed_ed25519"


def test_pages_deploy_requires_explicit_sha_bound_authorization():
    raw = WORKFLOW.read_text(encoding="utf-8")
    trigger_block = raw.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_run:" not in trigger_block
    assert "schedule:" not in trigger_block
    assert "\n  push:" not in trigger_block
    assert "expected_sha:" in trigger_block
    assert "authorization:" in trigger_block
    assert 'test "$AUTHORIZATION" = "DEPLOY_PAGES"' in raw
    assert 'test "$EVENT_REF" = "refs/heads/main"' in raw
    assert "repos/${GITHUB_REPOSITORY}/commits/main" in raw
    assert 'test "$main_head" = "$EXPECTED_SHA"' in raw
    assert "ref: ${{ inputs.expected_sha }}" in raw
    assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"' in raw
    assert "teams-notification-dashboard.yml/runs?status=success" in raw


def test_public_access_validation_runs_after_merged_pr_close():
    workflow = (ROOT / ".github" / "workflows" / "validacao-acessos.yml").read_text(encoding="utf-8")
    trigger_block = workflow.split("permissions:", 1)[0]
    assert "pull_request:" in trigger_block
    assert "types:" in trigger_block
    assert "- closed" in trigger_block
    assert "workflow_run:" not in trigger_block
    assert "github.event.pull_request.merged == true" in workflow
    assert "github.event.pull_request.merge_commit_sha" in workflow
    assert 'test "$observed_sha" = "$EXPECTED_SHA"' in workflow
    assert "ACCESS_VALIDATION_FAIL_ON_UNAVAILABLE" in workflow


def test_ci_locator_resolver_proves_fail_closed_negative_cases():
    result = subprocess.run(
        ["node", str(RESOLVER), "--self-test"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert '"self_test":true' in result.stdout.replace(" ", "")


def test_ci_locator_uses_same_public_identity_as_pages():
    html = HTML.read_text(encoding="utf-8")
    resolver = RESOLVER.read_text(encoding="utf-8")
    assert 'reqsys-dev-locator-2b0950c3bf37ac05b46bdb70ab793ca4c85b220b' in html
    assert 'reqsys-dev-locator-2b0950c3bf37ac05b46bdb70ab793ca4c85b220b' in resolver
    assert 'xMQwHfokBxBOkP1bvDCxBDdzmnXlVxApGQbwQ9h8kr8=' in html
    assert 'xMQwHfokBxBOkP1bvDCxBDdzmnXlVxApGQbwQ9h8kr8=' in resolver


def test_automatic_promotion_resolves_current_locator_instead_of_static_quick_tunnel():
    raw = PROMOTION.read_text(encoding="utf-8")
    job = raw.split("  validate-dev-pc24x7:", 1)[1].split("\n  dev-result:", 1)[0]
    assert "resolve_pc24x7_dev_locator.mjs --self-test" in job
    assert "--output artifacts/pc24x7-dev/signed-locator.json" in job
    assert "steps.locator.outputs.base_url" in job
    assert "steps.locator.outputs.frontend_url" in job
    assert "vars.PC24X7_DEV_BASE_URL" not in job
    assert "vars.PC24X7_DEV_FRONTEND_URL" not in job


def test_publisher_requires_complete_runtime_contract_before_locator():
    raw = PUBLISHER.read_text(encoding="utf-8")
    assert '"/api/health"' in raw
    assert '"/api/runtime/health"' in raw
    assert '"/api/runtime/readiness"' in raw
    assert '"/api/runtime/build-info"' in raw
    assert "def runtime_contract_ready" in raw
    assert 'probe_status(base_url, "/task-console") == 200' in raw
    assert 'probe_status(base_url, "/@vite/client") == 404' in raw
    assert "and runtime_contract_ready(value)" in raw
    assert '"runtime_contract_required": True' in raw
    assert '"static_frontend_required": True' in raw
    assert '"vite_hmr_forbidden": True' in raw


def test_supervisor_does_not_publish_when_runtime_contract_is_partial():
    raw = SUPERVISOR.read_text(encoding="utf-8")
    assert 'probe(LOCAL_GATEWAY + "/api/runtime/health")' in raw
    assert 'probe(LOCAL_GATEWAY + "/api/runtime/build-info")' in raw
    assert 'probe(LOCAL_GATEWAY + "/api/runtime/readiness")' in raw
    assert 'probe(LOCAL_GATEWAY + "/@vite/client")' in raw
    assert '"local_runtime_contract_failed"' in raw
    assert 'payload["local_runtime_contract_ready"] = local_ready' in raw
    assert 'payload["ready"] = local_ready and cloudflare_ready and (locator_ready if args.apply else True)' in raw
