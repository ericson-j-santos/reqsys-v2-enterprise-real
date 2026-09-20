import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "public-dev-locator" / "index.html"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-reqsys-pages-composite.yml"
SUPERVISOR = ROOT / "scripts" / "pc24x7_dev_runtime_supervisor.py"
INSTALLER = ROOT / "scripts" / "pc24x7_dev_runtime_supervisor_install.py"
MANIFEST = ROOT / "infra" / "public-access-urls.json"


def test_locator_requires_valid_signed_fresh_cloudflare_state():
    raw = HTML.read_text(encoding="utf-8")
    assert "Ed25519" in raw
    assert "expires_at" in raw
    assert "environment!==\"dev\"" in raw
    assert '.endsWith(".trycloudflare.com")' in raw
    assert "signature_b64" in raw
    assert "reqsys-dev-locator-" in raw
    assert "PRIVATE" not in raw.upper()


def test_pages_composite_publishes_stable_dev_path():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert '"docs/public-dev-locator/**"' in raw
    assert "cp -a docs/public-dev-locator/. site/dev/" in raw
    assert "test -s site/dev/index.html" in raw


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


def test_pages_redeploys_after_governed_pr_automation():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "Governed PR Automation" in raw
    assert "WORKFLOW_RUN_NAME" in raw
    assert 'WORKFLOW_RUN_NAME" == "Teams Notification Dashboard"' in raw
    assert 'WORKFLOW_RUN_NAME" == "Governed PR Automation"' in raw
    assert 'source="governed_pr_automation"' in raw
    assert "teams-notification-dashboard.yml/runs?status=success" in raw
