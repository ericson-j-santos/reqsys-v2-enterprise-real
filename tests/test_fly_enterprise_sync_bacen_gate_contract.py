from pathlib import Path


WORKFLOW = Path(".github/workflows/fly-enterprise-sync.yml")


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_prod_deploy_uses_reusable_bacen_gate():
    workflow = text()
    gate_start = workflow.index("\n  production-gate:\n")
    plan_start = workflow.index("\n  plan-environments:\n")
    gate_block = workflow[gate_start:plan_start]

    assert "REQSYS_PRODUCTION_GOVERNANCE_GATE" in workflow
    assert "inputs.deploy == true" in gate_block
    assert "inputs.target_environment == 'prod'" in gate_block
    assert "uses: ./.github/workflows/bacen-production-hard-gate.yml" in gate_block
    assert "enforce: true" in gate_block


def test_planning_requires_gate_success_or_nonprod_skip():
    workflow = text()
    start = workflow.index("\n  plan-environments:\n")
    end = workflow.index("\n  sync-environment:\n", start)
    block = workflow[start:end]

    assert "needs: [validate-manifest, publication-sync-gate, production-gate]" in block
    assert "needs.production-gate.result == 'success'" in block
    assert "needs.production-gate.result == 'skipped'" in block


def test_dev_hml_and_read_only_paths_are_preserved():
    workflow = text()
    assert "options: [dev, hml, prod]" in workflow
    assert "github.event.inputs.deploy != 'true'" in workflow
    assert "dev) GH_ENV=dev" in workflow
    assert "hml) GH_ENV=staging" in workflow
    assert "Verificar drift dev/hml (read-only)" in workflow


def test_secrets_and_deploy_remain_after_authorized_plan():
    workflow = text()
    plan = workflow.index("\n  plan-environments:\n")
    sync = workflow.index("\n  sync-environment:\n")
    secret = workflow.index("secrets.FLY_API_TOKEN", sync)
    deploy = workflow.index("flyctl deploy", sync)
    assert plan < sync < secret < deploy


def test_summary_exposes_production_gate_result():
    workflow = text()
    assert "BACEN production gate" in workflow
    assert "needs.production-gate.result" in workflow
