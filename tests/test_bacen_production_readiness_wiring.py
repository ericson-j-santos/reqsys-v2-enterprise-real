from pathlib import Path


def test_production_hard_gate_composes_gate2_before_authorizing_prod() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/bacen-production-hard-gate.yml").read_text(encoding="utf-8")

    assert "scripts/validate_bacen_production_readiness.py" in workflow
    assert "artifacts/bacen-production-hard-gate/gate2.json" in workflow
    assert "legacy_allowed and gate2_allowed" in workflow
    assert "main_branch_blocked_by_institutional_debt" in workflow
    assert "inputs.enforce" in workflow


def test_real_fly_production_sync_calls_the_composite_hard_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/fly-enterprise-sync.yml").read_text(encoding="utf-8")

    assert "inputs.target_environment == 'prod'" in workflow
    assert "uses: ./.github/workflows/bacen-production-hard-gate.yml" in workflow
    assert "enforce: true" in workflow
