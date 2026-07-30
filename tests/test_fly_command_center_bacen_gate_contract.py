from pathlib import Path


WORKFLOW = Path(".github/workflows/fly-governed-command-center.yml")


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_mutable_production_commands_use_reusable_gate():
    workflow = text()
    gate_start = workflow.index("\n  production-gate:\n")
    command_start = workflow.index("\n  governed-command:\n")
    assert "REQSYS_PRODUCTION_GOVERNANCE_GATE" in workflow
    assert gate_start < command_start
    assert "inputs.environment == 'production'" in workflow[gate_start:command_start]
    for command in ("deploy", "restart", "scale-count"):
        assert f"inputs.command == '{command}'" in workflow[gate_start:command_start]
    assert "uses: ./.github/workflows/bacen-production-hard-gate.yml" in workflow
    assert "enforce: true" in workflow


def test_secret_is_materialized_only_after_gate_result():
    workflow = text()
    governed_start = workflow.index("\n  governed-command:\n")
    secret = workflow.index("secrets.FLY_API_TOKEN", governed_start)
    block = workflow[governed_start:secret]
    assert "needs: production-gate" in block
    assert "needs.production-gate.result == 'success'" in block
    assert "needs.production-gate.result == 'skipped'" in block


def test_read_only_commands_remain_outside_mutation_gate():
    workflow = text()
    gate_start = workflow.index("\n  production-gate:\n")
    command_start = workflow.index("\n  governed-command:\n")
    gate_block = workflow[gate_start:command_start]
    for command in ("status", "logs", "secrets-list"):
        assert f"inputs.command == '{command}'" not in gate_block


def test_existing_confirmation_and_allowlist_remain_present():
    workflow = text()
    assert "CONFIRMO_EXECUCAO_FLY" in workflow
    assert "status|logs|deploy|restart|scale-count|secrets-list" in workflow
    assert "Produção exige gate BACEN para deploy, restart e scale-count." in workflow
