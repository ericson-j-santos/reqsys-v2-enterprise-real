from pathlib import Path


WORKFLOW = Path(".github/workflows/fly-runtime-p0.yml")


def test_reusable_bacen_gate_precedes_production_job():
    text = WORKFLOW.read_text(encoding="utf-8")
    gate = text.index("production-gate:")
    environment = text.index("environment: production")
    secret = text.index("secrets.FLY_API_TOKEN")
    deploy = text.index("flyctl deploy")

    assert "REQSYS_PRODUCTION_GOVERNANCE_GATE" in text
    assert "uses: ./.github/workflows/bacen-production-hard-gate.yml" in text
    assert "enforce: true" in text
    assert gate < environment < secret < deploy


def test_deploy_requires_validation_and_gate_success():
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("\n  deploy:\n")
    end = text.index("\n  public-smoke:\n", start)
    block = text[start:end]

    assert "needs: [validate-config, production-gate]" in block
    assert "needs.validate-config.result == 'success'" in block
    assert "needs.production-gate.result == 'success'" in block
    assert "inputs.deploy == true" in block


def test_validation_and_read_only_smoke_remain_available():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "validate-config:" in text
    assert "inputs.deploy == false || needs.deploy.result == 'success'" in text
    assert "--probe" in text
