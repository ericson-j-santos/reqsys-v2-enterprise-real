from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/todo-global-hourly-cycle.yml"
GATEWAY = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
SOURCE = ROOT / "scripts/todo_producer_keyvault_credit_gate.py"


def lane() -> str:
    raw = WORKFLOW.read_text(encoding="utf-8")
    return raw.split("  credential-dev:\n", 1)[1]


def test_workflow_keeps_existing_cycle_and_runtime_paths():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "  cycle:\n" in raw
    assert "  reconcile-runtime:\n" in raw
    assert "  public-e2e:\n" in raw
    assert "default: \"cycle\"" in raw
    assert "          - reconcile-runtime" in raw
    assert "          - producer-credit-gated" in raw
    assert "authorization_comment_id:" in raw
    assert "workflow_dispatch:" in raw
    assert "issue_comment:" not in raw


def test_gateway_proves_exact_owner_comment_and_typed_dispatch():
    raw = GATEWAY.read_text(encoding="utf-8")
    assert "github.event.issue.number == 1705" in raw
    assert "github.event.comment.user.login == 'ericson-j-santos'" in raw
    assert "github.event.comment.body == '/reqsys run todo-producer-keyvault-dev'" in raw
    assert "'/reqsys run todo-producer-keyvault-dev')" in raw
    assert "mode='producer-credit-gated'" in raw
    assert 'AUTHORIZED_COMMENT_ID: ${{ github.event.comment.id }}' in raw
    assert "-f operation=producer-credit-gated" in raw
    assert '-f authorization_comment_id="$AUTHORIZED_COMMENT_ID"' in raw
    assert "cycle|reconcile-runtime) ;;" in raw
    assert "-f secret=" not in raw
    assert "-f token=" not in raw


def test_hosted_oidc_recovery_is_isolated_from_physical_deploy_jobs():
    text = lane()
    assert "inputs.operation == 'producer-credit-gated'" in text
    assert "github.actor == 'github-actions[bot]'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "needs: contract" in text
    assert "runs-on: ubuntu-24.04" in text
    assert "environment: development" in text
    assert "id-token: write" in text
    assert "issues: read" in text
    assert "contents: read" in text
    assert "actions: write" not in text
    assert "self-hosted" not in text
    assert "secrets." not in text
    assert "uses: azure/login@a641126d1b8aa4d1fa005f4f92df94a3a4c4c906" in text


def test_secret_stage_runs_only_after_arm_cost_preflight():
    text = lane()
    first = "todo_producer_keyvault_credit_gate.py cost"
    second = "todo_producer_keyvault_credit_gate.py secret"
    assert text.index(first) < text.index(second)
    assert "set -euo pipefail" in text
    assert "az keyvault secret set" not in text
    assert "az role assignment create" not in text
    assert "docker" not in text.lower().split("      - name: publicar status")[0]
    assert "deploy " not in text.split("      - name: Publicar status")[0]


def test_script_rejects_missing_hard_stop_and_forbids_plaintext_args():
    src = SOURCE.read_text(encoding="utf-8")
    assert 'policy.get("spendingLimit") == "On"' in src
    assert 'value.get("state") == "Enabled"' in src
    assert '"COST_ZERO_CONFIRMED"' in src
    assert '"--file", str(value_file)' in src
    assert '"--value"' not in src
    assert "secrets.token_urlsafe(48)" in src
    assert "metadata_lookup(deleted=True)" in src
    assert "verify_owner_comment(ctx, os.environ)" in src
    assert "cost_preflight(ctx)" in src
    assert '"runtime_binding_verified": False' in src


def test_hourly_cycle_requires_arm_cost_gate_before_keyvault_lookup():
    raw = WORKFLOW.read_text(encoding="utf-8")
    cycle = raw.split("  cycle:\n", 1)[1].split("\n  credential-dev:\n", 1)[0]
    assert "github.event_name == 'schedule'" in cycle
    assert cycle.index("todo_producer_keyvault_credit_gate.py cycle-cost") < cycle.index(
        "az keyvault secret show")
    assert cycle.index("Login Azure por OIDC") < cycle.index(
        "todo_producer_keyvault_credit_gate.py cycle-cost")
    script = SOURCE.read_text(encoding="utf-8")
    assert '"cycle-cost"' in script
    assert "validate_cycle_cost_context" in script
    assert "cost_preflight(ctx)" in script
