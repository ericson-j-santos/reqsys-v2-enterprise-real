from pathlib import Path

DELIVERY = Path(".github/workflows/padrao-ouro-delivery-automation.yml")
REUSABLE = Path(".github/workflows/bacen-production-hard-gate.yml")


def test_productive_jobs_require_bacen_authorization() -> None:
    delivery = DELIVERY.read_text(encoding="utf-8")
    reusable = REUSABLE.read_text(encoding="utf-8")
    gate = delivery.index("\n  production-gate:\n")
    secrets_job = delivery.index("\n  configure-prod-secrets:\n")

    assert delivery.startswith("# REQSYS_PRODUCTION_GOVERNANCE_GATE\n")
    assert gate < secrets_job
    assert "uses: ./.github/workflows/bacen-production-hard-gate.yml" in delivery
    assert delivery.count("needs.production-gate.outputs.production_allowed == 'true'") >= 3
    assert "| BACEN production gate |" in delivery
    assert "  auto-open-pr:" in delivery
    assert "production_allowed:" in reusable
    assert "decision:" in reusable
    assert "value: ${{ jobs.gate.outputs.production_allowed }}" in reusable
