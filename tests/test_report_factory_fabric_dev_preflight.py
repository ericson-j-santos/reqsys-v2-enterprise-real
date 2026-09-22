from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "report-factory-fabric-dev-preflight.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_preflight_uses_existing_governed_oidc_identity_without_secret() -> None:
    text = _text()
    assert "environment: development" in text
    assert "id-token: write" in text
    assert "CCP_AZURE_CLIENT_ID" in text
    assert "CCP_AZURE_TENANT_ID" in text
    assert "CCP_AZURE_SUBSCRIPTION_ID" in text
    assert "azure/login@7184910d9eb2b1c5e48f7073824a90609bb9b6d6" in text
    assert "client-secret:" not in text
    assert "FABRIC_ACCESS_TOKEN" not in text
    assert "pull_request_target" not in text


def test_preflight_is_read_only_and_reuses_canonical_probe() -> None:
    text = _text()
    assert "scripts/fabric_oidc_readonly_probe.py" in text
    assert "mutations_performed=false" in text
    assert "secret_value_exposed=false" in text
    assert "fabric.get(\"status\") == 200" in text
    forbidden = ("az ad app create", "roleAssignments", "--method post", "--method patch", "--method delete")
    for marker in forbidden:
        assert marker not in text
