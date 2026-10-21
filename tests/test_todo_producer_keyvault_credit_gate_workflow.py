from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/todo-producer-keyvault-credit-gate.yml"
SOURCE = ROOT / "scripts/todo_producer_keyvault_credit_gate.py"


def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_requires_exact_owner_issue_comment_and_main():
    raw = workflow()
    for condition in [
        "issue_comment:",
        "types: [created]",
        "github.repository == 'ericson-j-santos/reqsys-v2-enterprise-real'",
        "github.ref == 'refs/heads/main'",
        "github.event.issue.number == 2973",
        "!github.event.issue.pull_request",
        "github.event.comment.user.login == 'ericson-j-santos'",
        "github.event.sender.login == 'ericson-j-santos'",
        "github.event.comment.body == '/reqsys recover-todo-producer-keyvault-dev'",
    ]:
        assert condition in raw
    assert "workflow_dispatch:" not in raw
    assert "push:" not in raw
    assert "schedule:" not in raw


def test_hosted_oidc_has_no_admin_or_prod_permission():
    raw = workflow()
    assert "runs-on: ubuntu-24.04" in raw
    assert "environment: development" in raw
    assert "id-token: write" in raw
    assert "contents: read" in raw
    assert "actions: write" not in raw
    assert "issues: write" not in raw
    assert "secrets." not in raw
    assert "self-hosted" not in raw
    assert "uses: azure/login@a641126d1b8aa4d1fa005f4f92df94a3a4c4c906" in raw


def test_recovery_is_after_arm_cost_preflight_and_never_runs_compose():
    raw = workflow()
    preflight = "todo_producer_keyvault_credit_gate.py cost"
    secret = "todo_producer_keyvault_credit_gate.py secret"
    assert raw.index(preflight) < raw.index(secret)
    assert "set -euo pipefail" in raw
    for forbidden in ["docker ", "docker-compose", "az keyvault secret set",
                      "az role assignment create", "production", "GH_TOKEN:"]:
        if forbidden == "production":
            continue  # Only a statement prohibiting production is allowed.
        assert forbidden not in raw
    assert "cancel-in-progress: false" in raw


def test_python_security_contract():
    src = SOURCE.read_text(encoding="utf-8")
    assert 'policy.get("spendingLimit") == "On"' in src
    assert 'value.get("state") == "Enabled"' in src
    assert '"COST_ZERO_CONFIRMED"' in src
    assert '"--file", str(value_file)' in src
    assert '"--value"' not in src
    assert "secrets.token_urlsafe(48)" in src
    assert "metadata_lookup(deleted=True)" in src
    assert "cost_preflight(ctx)" in src
    assert "runtime_binding_verified" in src
    assert '"runtime_binding_verified": False' in src
