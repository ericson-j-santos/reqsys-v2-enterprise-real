import base64
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "public-dev-locator" / "index.html"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-reqsys-pages-composite.yml"
RELAY_WORKFLOW = ROOT / ".github" / "workflows" / "dispatch-public-runtime-evidence.yml"
SUPERVISOR = ROOT / "scripts" / "pc24x7_dev_runtime_supervisor.py"
INSTALLER = ROOT / "scripts" / "pc24x7_dev_runtime_supervisor_install.py"
MANIFEST = ROOT / "infra" / "public-access-urls.json"
PUBLISHER = ROOT / "scripts" / "pc24x7_dev_locator_publisher.py"
RESOLVER = ROOT / "scripts" / "resolve_pc24x7_dev_locator.mjs"
PROMOTION = ROOT / ".github" / "workflows" / "fly-automatic-environment-promotion.yml"
PC24X7_COMPOSE = ROOT / "docker-compose.pc24x7-public-dev.yml"


def load_publisher():
    spec = importlib.util.spec_from_file_location("pc24x7_dev_locator_publisher_test", PUBLISHER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_locator_requires_valid_signed_fresh_cloudflare_state():
    raw = HTML.read_text(encoding="utf-8")
    assert "Ed25519" in raw
    assert "expires_at" in raw
    assert "environment!==\"dev\"" in raw
    assert '.endsWith(".trycloudflare.com")' in raw
    assert "signature_b64" in raw
    assert 'contract.version!=="2.0.0"' in raw
    assert "static_frontend_required!==true" in raw
    assert "vite_hmr_forbidden!==true" in raw
    assert '"/api/runtime/readiness"' in raw
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
    assert "cp -a frontend/dist/. site/dev/" in raw
    assert "VITE_BASE_PATH: /reqsys-v2-enterprise-real/dev/" in raw
    assert "test -s site/dev/index.html" in raw
    assert "test -s site/dev/runtime-locator.json" in raw
    assert "actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e" in raw


def test_pc24x7_public_runtime_enables_entra_and_disables_demo_login():
    raw = PC24X7_COMPOSE.read_text(encoding="utf-8")
    assert 'ALLOW_DEMO_LOGIN: "false"' in raw
    assert "AZURE_TENANT_ID: 6d09c88c-0617-490c-8329-305e577684bc" in raw
    assert "AZURE_CLIENT_ID: 4061c542-cdc1-4007-ab57-40ab8f9109fc" in raw
    assert "APP_PUBLIC_URL: https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev" in raw
    assert "https://ericson-j-santos.github.io" in raw


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


def test_public_access_validation_requires_runtime_sha_only_for_deploy_scope():
    workflow = (ROOT / ".github" / "workflows" / "validacao-acessos.yml").read_text(encoding="utf-8")
    assert "validacao-acessos-${{ github.event_name }}-" in workflow
    assert "github.event.pull_request.number || github.sha" in workflow
    assert "validacao-acessos-${{ github.ref }}" not in workflow
    assert ".github/scripts/classify_public_access_runtime_scope.py" in workflow
    assert '"/api/runtime/build-info"' in workflow
    assert 'git diff --no-renames --name-only "$observed_sha" "$EXPECTED_SHA" --' in workflow
    assert "--scope-available" in workflow
    assert "RUNTIME_SHA_REQUIRED: ${{ steps.runtime_scope.outputs.runtime_sha_required }}" in workflow
    assert "CLASSIFIED_OBSERVED_SHA: ${{ steps.runtime_scope.outputs.observed_sha }}" in workflow
    assert 'if observed != classified_observed:' in workflow
    assert "if runtime_sha_required and observed != expected:" in workflow
    assert 'final_status, final_body, final_latency = get("/api/runtime/build-info")' in workflow
    assert 'if final_observed != classified_observed:' in workflow
    assert 'raise SystemExit("build_sha_changed_after_validation")' in workflow
    assert '"health_strict_sha_informational"' in workflow


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


def test_ci_locator_resolver_can_be_imported_from_node_stdin():
    result = subprocess.run(
        ["node", "--input-type=module"],
        cwd=ROOT,
        input=(
            "import { verifyEnvelope } from "
            "'./scripts/resolve_pc24x7_dev_locator.mjs';\n"
            "if (typeof verifyEnvelope !== 'function') throw new Error('verifyEnvelope_missing');\n"
            "process.stdout.write('resolver_import_ok\\n');\n"
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "resolver_import_ok\n"


def test_ci_locator_uses_same_public_identity_as_pages():
    html = HTML.read_text(encoding="utf-8")
    resolver = RESOLVER.read_text(encoding="utf-8")
    publisher = load_publisher()
    runtime_config = json.loads((ROOT / "frontend" / "public" / "runtime-locator.json").read_text(encoding="utf-8"))
    assert runtime_config["topic"] in html
    assert runtime_config["topic"] in resolver
    assert runtime_config["topic"] == publisher.PINNED_TOPIC
    assert runtime_config["public_key_b64"] in html
    assert runtime_config["public_key_b64"] in resolver
    assert runtime_config["public_key_b64"] == publisher.PINNED_PUBLIC_KEY_B64


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
    assert "def static_frontend_ready" in raw
    assert "and static_frontend_ready(base_url)" in raw
    assert '"/assets/" in html' in raw
    assert '"/src/main.js" not in html' in raw
    assert 'probe_status(base_url, "/@vite/client") == 404' in raw
    assert "allowed_runtime_url(normalized) and runtime_contract_ready(normalized)" in raw
    assert '"runtime_contract_required": True' in raw
    assert '"static_frontend_required": True' in raw
    assert '"vite_hmr_forbidden": True' in raw
    assert '"runtime_contract": {' in raw
    assert '"version": "2.0.0"' in raw
    assert '"required_endpoints": list(REQUIRED_PUBLIC_ENDPOINTS)' in raw
    assert "class RejectRedirectHandler" in raw
    assert raw.count("with open_no_redirect(") == 4


def test_publisher_rejects_noncanonical_state_urls_before_any_probe(monkeypatch, tmp_path):
    publisher = load_publisher()
    valid = "https://valid-primary.trycloudflare.com"
    state = tmp_path / "dev-tunnels.json"
    state.write_text(
        json.dumps({
            "tunnels": [
                {"url": "https://valid.trycloudflare.com/unexpected"},
                {"url": "https://user@valid.trycloudflare.com"},
                {"url": "https://valid.trycloudflare.com:443"},
                {"url": "https://valid.trycloudflare.com.evil.example"},
                {"url": 42},
                {"url": valid},
            ],
        }),
        encoding="utf-8",
    )
    probed = []
    monkeypatch.setattr(publisher, "CF_STATE", state)
    monkeypatch.setattr(
        publisher,
        "runtime_contract_ready",
        lambda value: probed.append(value) or True,
    )

    assert publisher.healthy_urls() == [valid]
    assert probed == [valid]
    assert publisher.RejectRedirectHandler().redirect_request(
        None, None, 302, "redirect", {}, "https://elsewhere.example"
    ) is None


def test_publisher_identity_missing_or_partial_fails_without_overwrite(monkeypatch, tmp_path):
    publisher = load_publisher()

    missing_dir = tmp_path / "missing"
    monkeypatch.setattr(publisher, "KEY_BLOB", missing_dir / "dev-locator-key.dpapi")
    monkeypatch.setattr(publisher, "PUBLIC_CFG", missing_dir / "dev-locator-public.json")
    with pytest.raises(RuntimeError, match="pinned_locator_identity_missing"):
        publisher.ensure_identity()
    assert not missing_dir.exists()

    partial_dir = tmp_path / "partial"
    partial_dir.mkdir()
    key_blob = partial_dir / "dev-locator-key.dpapi"
    public_cfg = partial_dir / "dev-locator-public.json"
    key_blob.write_bytes(b"must-not-change")
    monkeypatch.setattr(publisher, "KEY_BLOB", key_blob)
    monkeypatch.setattr(publisher, "PUBLIC_CFG", public_cfg)
    with pytest.raises(RuntimeError, match="locator_identity_partial_state"):
        publisher.ensure_identity()
    assert key_blob.read_bytes() == b"must-not-change"
    assert not public_cfg.exists()


def test_publisher_rejects_identity_topic_config_and_private_key_mismatch(monkeypatch):
    publisher = load_publisher()
    key = Ed25519PrivateKey.generate()
    other_key = Ed25519PrivateKey.generate()
    key_public = publisher.public_identity(key)
    other_public = publisher.public_identity(other_key)

    monkeypatch.setattr(publisher, "PINNED_PUBLIC_KEY_B64", key_public)
    with pytest.raises(RuntimeError, match="locator_topic_not_pinned"):
        publisher.validate_pinned_identity(key, {
            "topic": "reqsys-dev-locator-wrong",
            "public_key_b64": key_public,
        })

    with pytest.raises(RuntimeError, match="locator_public_key_config_not_pinned"):
        publisher.validate_pinned_identity(key, {
            "topic": publisher.PINNED_TOPIC,
            "public_key_b64": other_public,
        })

    monkeypatch.setattr(publisher, "PINNED_PUBLIC_KEY_B64", other_public)
    with pytest.raises(RuntimeError, match="locator_private_key_does_not_match_pinned_public_key"):
        publisher.validate_pinned_identity(key, {
            "topic": publisher.PINNED_TOPIC,
            "public_key_b64": other_public,
        })

    accepted_key, accepted_cfg = publisher.validate_pinned_identity(other_key, {
        "topic": publisher.PINNED_TOPIC,
        "public_key_b64": other_public,
    })
    assert accepted_key is other_key
    assert accepted_cfg["public_key_b64"] == other_public

    with pytest.raises(ValueError, match="invalid_locator_topic"):
        publisher.publish_envelope("reqsys-dev-locator-wrong", b"public-envelope")


@pytest.mark.parametrize(
    ("body", "content_type", "expected"),
    [
        (b'<html><script src="/assets/index.js"></script></html>', "text/html", True),
        (b'<html><script src="/src/main.js"></script></html>', "text/html", False),
        (b'<html><script src="/assets/index.js"></script></html>', "application/json", False),
        (b"\xff/assets/", "text/html", False),
    ],
)
def test_publisher_proves_static_frontend_content_before_signing(
    monkeypatch,
    body,
    content_type,
    expected,
):
    publisher = load_publisher()

    class FakeResponse:
        status = 200
        headers = {"Content-Type": content_type}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return body

    monkeypatch.setattr(
        publisher,
        "open_no_redirect",
        lambda _request, *, timeout: FakeResponse(),
    )
    assert publisher.static_frontend_ready("https://valid.trycloudflare.com") is expected


def test_sign_only_relay_writes_public_envelope_without_publish_or_state(
    monkeypatch,
    tmp_path,
    capsys,
):
    publisher = load_publisher()
    key = Ed25519PrivateKey.generate()
    public_key_b64 = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )).decode("ascii")
    monkeypatch.setattr(
        publisher,
        "ensure_identity",
        lambda: (key, {
            "topic": "reqsys-dev-locator-test",
            "public_key_b64": public_key_b64,
        }),
    )
    monkeypatch.setattr(
        publisher,
        "healthy_urls",
        lambda: ["https://valid-primary.trycloudflare.com", "https://valid-failover.trycloudflare.com"],
    )
    monkeypatch.setattr(
        publisher,
        "publish_envelope",
        lambda *_args, **_kwargs: pytest.fail("sign-only tentou publicar no ntfy"),
    )
    state = tmp_path / "publish-state.json"
    output = tmp_path / "signed-envelope.json"
    monkeypatch.setattr(publisher, "PUBLISH_STATE", state)

    assert publisher.main(["--sign-only", "--envelope-output", str(output)]) == 0
    assert output.is_file()
    assert not state.exists()
    raw_envelope = output.read_bytes()
    assert len(raw_envelope) <= publisher.MAX_RELAY_ENVELOPE_BYTES
    envelope = json.loads(raw_envelope)
    assert set(envelope) == {"v", "payload_b64", "signature_b64"}
    key.public_key().verify(
        base64.b64decode(envelope["signature_b64"]),
        envelope["payload_b64"].encode("ascii"),
    )
    payload = json.loads(base64.b64decode(envelope["payload_b64"]))
    assert payload["environment"] == "dev"
    assert payload["selected_url"] == "https://valid-primary.trycloudflare.com"
    assert payload["expires_at"] - payload["issued_at"] == 900
    assert payload["runtime_contract"]["version"] == "2.0.0"
    stdout = capsys.readouterr().out
    assert '"relay_ready": true' in stdout
    assert "payload_b64" not in stdout
    assert "signature_b64" not in stdout
    assert "private" not in stdout.lower()


def test_sign_only_relay_fails_closed_without_healthy_url(monkeypatch, tmp_path, capsys):
    publisher = load_publisher()
    monkeypatch.setattr(
        publisher,
        "ensure_identity",
        lambda: (Ed25519PrivateKey.generate(), {
            "topic": "reqsys-dev-locator-test",
            "public_key_b64": "public-test",
        }),
    )
    monkeypatch.setattr(publisher, "healthy_urls", lambda: [])
    monkeypatch.setattr(
        publisher,
        "publish_envelope",
        lambda *_args, **_kwargs: pytest.fail("relay sem URL tentou publicar"),
    )
    output = tmp_path / "must-not-exist.json"
    state = tmp_path / "must-not-touch-state.json"
    monkeypatch.setattr(publisher, "PUBLISH_STATE", state)

    assert publisher.main(["--sign-only", "--envelope-output", str(output)]) == 2
    assert not output.exists()
    assert not state.exists()
    stdout = capsys.readouterr().out
    assert "no_healthy_runtime_urls" in stdout
    assert "payload_b64" not in stdout
    assert "signature_b64" not in stdout


def test_sign_only_relay_rejects_unpaired_cli_arguments():
    publisher = load_publisher()
    with pytest.raises(SystemExit):
        publisher.parse_args(["--sign-only"])
    with pytest.raises(SystemExit):
        publisher.parse_args(["--envelope-output", "envelope.json"])


def test_sign_only_relay_rejects_noncanonical_runtime_urls():
    publisher = load_publisher()
    with pytest.raises(ValueError, match="no_healthy_runtime_urls"):
        publisher.build_payload([], now_epoch=2_000_000_000)
    for invalid in (
        "http://invalid.trycloudflare.com",
        "https://trycloudflare.com",
        "https://valid.trycloudflare.com.evil.example",
        "https://user@valid.trycloudflare.com",
        "https://valid.trycloudflare.com:443",
        "https://valid.trycloudflare.com/unexpected",
    ):
        with pytest.raises(ValueError, match="invalid_runtime_url"):
            publisher.build_payload([invalid], now_epoch=2_000_000_000)


def test_github_hosted_locator_relay_is_manual_sha_bound_and_fail_closed():
    raw = RELAY_WORKFLOW.read_text(encoding="utf-8")
    trigger_block = raw.split("permissions:", 1)[0]
    retired_dispatch_job = raw.split("  dispatch-public-runtime-evidence:", 1)[1].split(
        "\n  relay:", 1
    )[0]
    assert "workflow_dispatch:" in trigger_block
    assert "operation:" in trigger_block
    assert 'default: "public-runtime-evidence"' in trigger_block
    assert '          - "relay-dev-locator"' in trigger_block
    assert "expected_sha:" in trigger_block
    assert "authorization:" in trigger_block
    assert "envelope_b64:" in trigger_block
    assert "schedule:" not in trigger_block
    assert "\n  push:" not in trigger_block
    assert "permissions:\n  contents: read" in raw
    assert "cancel-in-progress: false" in raw
    assert raw.count("timeout-minutes: 5") == 1
    assert "runs-on: ubuntu-latest" in raw
    assert "self-hosted" not in raw
    assert "RELAY_DEV_LOCATOR" in raw
    assert "Fly.io retirado definitivamente" in raw
    assert "if: ${{ false }}" in retired_dispatch_job
    assert retired_dispatch_job.count("\n    if:") == 1
    assert "inputs.operation" not in retired_dispatch_job
    assert "reqsys-api.fly.dev" not in trigger_block
    assert "if: ${{ inputs.operation == 'relay-dev-locator' }}" in raw
    assert "refs/heads/main" in raw
    assert 'test "$GITHUB_EVENT_NAME" = \'workflow_dispatch\'' in raw
    assert 'test "$GITHUB_SHA" = "$EXPECTED_SHA"' in raw
    assert "commits/main" in raw
    assert "main_sha_changed" in raw
    assert raw.index("Validate authorization and current main SHA before checkout") < raw.index(
        "Checkout exact authorized SHA"
    ) < raw.index("from './scripts/resolve_pc24x7_dev_locator.mjs'")
    assert raw.count("persist-credentials: false") == 1
    assert "${{ inputs.envelope_b64 }}" in raw
    assert "${{ needs." not in raw
    assert "relay_base64_noncanonical" in raw
    assert "relay_envelope_utf8_invalid" in raw
    assert "relay_envelope_size_invalid" in raw
    assert "verifyEnvelope" in raw
    assert "relay_ttl_below_300_seconds" in raw
    assert "relay_ttl_below_300_seconds_before_post" in raw
    assert raw.index("Preflight public DEV runtime before relay") < raw.index(
        "Revalidate TTL and publish once to the fixed ntfy DEV topic"
    )
    assert "--header 'Title: reqsys-dev-locator'" in raw
    assert "https://ntfy.sh/reqsys-dev-locator-1651e9182d6e1c939fa6672c1248c9d532716fe7" in raw
    assert "relay_topic_constant_mismatch" in raw
    assert "relay_title_constant_mismatch" in raw
    assert raw.count("--request POST") == 1
    assert "--retry" not in raw
    assert "--location" not in raw
    assert 'READBACK_MAX_ATTEMPTS: "6"' in raw
    assert 'READBACK_DELAY_SECONDS: "2"' in raw
    assert 'READBACK_REQUEST_MAX_SECONDS: "5"' in raw
    assert 'READBACK_DEADLINE_SECONDS: "40"' in raw
    assert 'for attempt in $(seq 1 "$READBACK_MAX_ATTEMPTS")' in raw
    assert 'readback_deadline_at=$((SECONDS + READBACK_DEADLINE_SECONDS))' in raw
    assert 'remaining_seconds=$((readback_deadline_at - SECONDS))' in raw
    assert '--max-time "$request_max_seconds"' in raw
    assert "exact_relay_envelope_readback_deadline_exceeded" in raw
    assert 'json?poll=1&id=$message_id' in raw
    assert "relay_publish_message_id_invalid" in raw
    assert "relay_publish_response_envelope_mismatch" in raw
    assert "safe.publish = {" in raw
    assert "item?.id !== expectedMessageId" in raw
    assert "process.exit(42)" in raw
    assert "exact_relay_envelope_not_found_after_bounded_poll" in raw
    assert raw.index("--request POST") < raw.index('for attempt in $(seq 1 "$READBACK_MAX_ATTEMPTS")')
    readback = raw.split("- name: Read back exact envelope and reverify", 1)[1].split(
        "- name: Cleanup relay temporary files", 1
    )[0]
    assert "--request POST" not in readback
    assert "--data-binary" not in readback
    assert "--max-filesize 65536" in readback
    assert 'test "$(wc -c < "$NTFY_READBACK_PATH")" -le 65536' in readback
    assert "exact_relay_envelope_not_found" in raw
    assert "exact_envelope_sha256" in raw
    assert "signature_reverified: true" in raw
    for endpoint in (
        "/api/health",
        "/api/runtime/health",
        "/api/runtime/readiness",
        "/api/runtime/build-info",
        "/task-console",
        "/@vite/client",
    ):
        assert endpoint in raw
    assert "runtime_sha_is_evidence_only = true" in raw
    assert "compared_to_control_plane_sha = false" in raw
    cleanup = raw.split("- name: Cleanup relay temporary files", 1)[1].split(
        "- name: Upload sanitized relay evidence", 1
    )[0]
    assert "if: always()" in cleanup
    assert "SIGNED_ENVELOPE_PATH" in cleanup
    assert "SAFE_METADATA_PATH" in cleanup
    assert "NTFY_RESPONSE_PATH" in cleanup
    assert "NTFY_READBACK_PATH" in cleanup
    upload = raw.split("- name: Upload sanitized relay evidence", 1)[1]
    assert "relay-evidence.json" in upload
    assert "signed-envelope" not in upload
    assert "envelope_in_evidence = false" in raw


def test_supervisor_does_not_publish_when_runtime_contract_is_partial():
    raw = SUPERVISOR.read_text(encoding="utf-8")
    assert 'probe(LOCAL_GATEWAY + "/api/runtime/health")' in raw
    assert 'probe(LOCAL_GATEWAY + "/api/runtime/build-info")' in raw
    assert 'probe(LOCAL_GATEWAY + "/api/runtime/readiness")' in raw
    assert 'probe(LOCAL_GATEWAY + "/@vite/client")' in raw
    assert '"local_runtime_contract_failed"' in raw
    assert 'payload["local_runtime_contract_ready"] = local_ready' in raw
    assert 'payload["ready"] = local_ready and cloudflare_ready and (locator_ready if args.apply else True)' in raw


def test_signed_locator_contract_v2_is_required_by_pages_and_ci_resolver():
    html = HTML.read_text(encoding="utf-8")
    resolver = RESOLVER.read_text(encoding="utf-8")
    publisher = PUBLISHER.read_text(encoding="utf-8")

    assert '"runtime_contract": {' in publisher
    assert '"version": "2.0.0"' in publisher
    assert 'contract.version!=="2.0.0"' in html
    assert 'payload?.runtime_contract?.version !== "2.0.0"' in resolver
    assert "self_test_legacy_locator_accepted" in resolver
    assert "reqsys-app-dev.fly.dev" not in html
    assert "reqsys-api-dev.fly.dev" not in html


def test_public_access_validation_resolves_locator_and_smokes_real_dev_same_sha():
    workflow = (ROOT / ".github" / "workflows" / "validacao-acessos.yml").read_text(encoding="utf-8")
    assert "resolve_pc24x7_dev_locator.mjs --self-test" in workflow
    assert "--output reports/pc24x7-dev/signed-locator.json" in workflow
    assert "steps.dev_locator.outputs.base_url" in workflow
    for endpoint in (
        "/api/health",
        "/api/runtime/health",
        "/api/runtime/readiness",
        "/api/runtime/build-info",
    ):
        assert endpoint in workflow
    assert "build_sha_mismatch" in workflow
    assert 'get("/task-console")' in workflow
    assert 'get("/@vite/client")' in workflow
    assert "frontend_not_static" in workflow
    assert "vite_hmr_exposed" in workflow
    assert "runtime-smoke.json" in workflow
    assert "path: reports/" in workflow


def test_locator_requires_critical_backend_routes_before_publication() -> None:
    raw = PUBLISHER.read_text(encoding="utf-8")
    assert "CRITICAL_ROUTE_PROBES" in raw
    assert '"/v1/cofre/runtime/control-status"' in raw
    assert '"/v1/teams-gateway/flow-bot/owners"' in raw
    assert "frozenset({401, 403})" in raw
    assert "def critical_route_ready" in raw
    assert "404/405/2xx inesperado falham" in raw
    assert "all(critical_route_ready" in raw
