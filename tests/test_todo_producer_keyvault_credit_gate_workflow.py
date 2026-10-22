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
    assert 'HARD_STOP_DECISION = "AZURE_SPENDING_LIMIT_ON_CONFIRMED"' in src
    assert '"literal_zero_cost_verified": False' in src
    assert '"keyvault_data_plane_allowed": False' in src
    assert "require_literal_zero(fresh)" in src
    assert '"COST_ZERO_CONFIRMED"' not in src
    assert '"--file", str(value_file)' in src
    assert '"--value"' not in src
    assert "secrets.token_urlsafe(48)" in src
    assert "metadata_lookup(deleted=True)" in src
    assert "verify_owner_comment(ctx, os.environ)" in src
    assert "cost_preflight(ctx)" in src
    assert '"runtime_binding_verified": False' in src


def test_hourly_cycle_blocks_before_any_keyvault_lookup_without_literal_zero():
    raw = WORKFLOW.read_text(encoding="utf-8")
    cycle = raw.split("  cycle:\n", 1)[1].split("\n  credential-dev:\n", 1)[0]
    assert "github.event_name == 'schedule'" in cycle
    assert "github.actor == 'ericson-j-santos'" in cycle
    assert cycle.count("todo_producer_keyvault_credit_gate.py cycle-secret") == 1
    assert "az keyvault secret show" not in cycle
    assert "keyvault secret" not in cycle.lower()
    assert "continue-on-error" not in cycle
    assert cycle.index("Login Azure por OIDC") < cycle.index(
        "todo_producer_keyvault_credit_gate.py cycle-secret")
    script = SOURCE.read_text(encoding="utf-8")
    assert '"cycle-secret"' in script
    assert "validate_cycle_cost_context" in script
    assert "cost_preflight(ctx)" in script
    assert "require_literal_zero(proof)" in script
    assert script.index("require_literal_zero(proof)") < script.index(
        "token = read_runtime_token()")


def test_token_is_validated_in_python_before_mask_or_github_env():
    raw = WORKFLOW.read_text(encoding="utf-8")
    public = raw.split("  public-e2e:\n", 1)[1].split("\n  cycle:\n", 1)[0]
    assert "todo_producer_keyvault_credit_gate.py export-token" in public
    assert "token=\"$(az keyvault" not in public
    assert "::add-mask::" not in public
    assert "TODO_GLOBAL_RUNTIME_TOKEN=%s" not in public
    source = SOURCE.read_text(encoding="utf-8")
    validation = source.index("canonical = validate_runtime_token(token)")
    mask = source.index('print(f"::add-mask::{canonical}")')
    sink = source.index('f"TODO_GLOBAL_RUNTIME_TOKEN={canonical}\\n"')
    assert validation < mask < sink
    assert '("\\r", "\\n", "\\x00")' in source


def test_manual_reconcile_blocks_before_sdk_or_public_keyvault_paths():
    raw = WORKFLOW.read_text(encoding="utf-8")
    reconcile = raw.split("  reconcile-runtime:\n", 1)[1].split(
        "\n  public-e2e:\n", 1)[0]
    public = raw.split("  public-e2e:\n", 1)[1].split("\n  cycle:\n", 1)[0]
    guard_call = "todo_producer_keyvault_credit_gate.py runtime-cost"
    reconciler = "scripts/reconcile_pc24x7_todo_runtime.py"
    assert "github.actor == 'ericson-j-santos'" in reconcile
    assert "github.actor == 'ericson-j-santos'" in public
    assert reconcile.count(guard_call) == 1
    assert reconcile.index("Login Azure por OIDC") < reconcile.index(guard_call)
    assert reconcile.index(guard_call) < reconcile.index(reconciler)
    assert "continue-on-error" not in reconcile
    assert "secrets.COFRE_ADMIN_JWT" not in reconcile.split(guard_call, 1)[0]
    assert "secrets.COFRE_ADMIN_JWT" in reconcile.split(guard_call, 1)[1]
    assert "todo_producer_keyvault_credit_gate.py export-token" in public
    source = SOURCE.read_text(encoding="utf-8")
    export_branch = source.split('if args.phase == "export-token":', 1)[1].split(
        'if args.phase == "runtime-cost":', 1)[0]
    assert export_branch.index("require_literal_zero(proof)") < export_branch.index(
        "token = read_runtime_token()")


def test_oidc_and_checkout_credentials_are_scoped_per_job():
    raw = WORKFLOW.read_text(encoding="utf-8")
    header = raw.split("jobs:\n", 1)[0]
    contract = raw.split("  contract:\n", 1)[1].split("\n  reconcile-runtime:\n", 1)[0]
    reconcile = raw.split("  reconcile-runtime:\n", 1)[1].split("\n  public-e2e:\n", 1)[0]
    public = raw.split("  public-e2e:\n", 1)[1].split("\n  cycle:\n", 1)[0]
    cycle = raw.split("  cycle:\n", 1)[1].split("\n  credential-dev:\n", 1)[0]
    assert "id-token: write" not in header
    assert "id-token: write" not in contract
    for job in (reconcile, public, cycle, lane()):
        assert "id-token: write" in job
    assert raw.count("uses: actions/checkout@") == raw.count(
        "persist-credentials: false")


def test_workflow_paths_cover_guard_implementation_contract_and_tests():
    raw = WORKFLOW.read_text(encoding="utf-8")
    push = raw.split("  push:\n", 1)[1].split("  pull_request:\n", 1)[0]
    pull_request = raw.split("  pull_request:\n", 1)[1].split(
        "  workflow_dispatch:\n", 1)[0]
    required = (
        "scripts/todo_producer_keyvault_credit_gate.py",
        "tests/test_todo_global_hourly_cycle.py",
        "tests/test_todo_producer_keyvault_credit_gate.py",
        "tests/test_todo_producer_keyvault_credit_gate_workflow.py",
        ".sdd/specs/todo-producer-keyvault-credit-gate.requirements.md",
        ".sdd/specs/todo-producer-keyvault-credit-gate.spec.json",
    )
    for path in required:
        assert path in push
        assert path in pull_request


def test_privileged_cli_attests_workflow_ref_and_workflow_sha():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'env.get("GITHUB_WORKFLOW_REF") == WORKFLOW_REF' in source
    assert 'workflow_sha == env.get("GITHUB_SHA")' in source
    assert "and workflow_identity_valid(env)" in source
