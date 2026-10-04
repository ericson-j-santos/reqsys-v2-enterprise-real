from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "report-factory-fabric-dev-access-bootstrap.yml"
SCRIPT = ROOT / "scripts" / "report_factory_fabric_dev_access_bootstrap.py"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"


def test_workflow_is_manual_dev_inputless_and_noteri_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "push:" not in text
    assert "if: github.ref == 'refs/heads/main'" in text
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in text
    assert "environment: development" in text
    assert "CCP_AZURE_CLIENT_ID: ${{ vars.CCP_AZURE_CLIENT_ID }}" in text
    assert "secrets." not in text


def test_script_has_fixed_workspace_contributor_and_idempotent_readback() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'WORKSPACE_NAME = "ReqSys - Observabilidade"' in text
    assert '{"role": "Contributor"}' in text
    assert '"type": "ServicePrincipal"' in text
    assert '"POST"' in text
    assert '"PATCH"' in text
    assert text.count("_list_roles(workspace_id, token)") >= 2
    assert "contributor_postcondition_failed" in text
    assert '"DELETE"' not in text
    assert "client secret" not in text.casefold()


def test_evidence_is_sanitized_and_nonprod() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"secret_value_exposed": False' in text
    assert '"identifiers_exposed": False' in text
    assert '"production_touched": False' in text
    assert 'print(f"reason={evidence[\'reason\']}")' in text
    assert "print(token" not in text
    assert "print(client_id" not in text
    assert "print(workspace_id" not in text
    assert 'print(f"workspace_id=' not in text
    assert 'print(f"client_id=' not in text


def test_self_hosted_policy_allowlists_bootstrap() -> None:
    text = POLICY.read_text(encoding="utf-8")
    assert ".github/workflows/report-factory-fabric-dev-access-bootstrap.yml" in text
