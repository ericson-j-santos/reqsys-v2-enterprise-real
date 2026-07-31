from pathlib import Path

WORKFLOW = Path(".github/workflows/fly-environment-homologation-gate.yml")


def test_bacen_gate_precedes_production_environment_and_secret() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    gate = text.index("\n  production-gate:\n")
    deploy = text.index("\n  deploy:\n")
    environment = text.index("    environment:\n", deploy)
    secret = text.index("FLY_API_TOKEN:", deploy)

    assert text.startswith("# REQSYS_PRODUCTION_GOVERNANCE_GATE\n")
    assert gate < deploy < environment < secret
    assert "inputs.environment == 'prod' && inputs.deploy == true" in text
    assert "uses: ./.github/workflows/bacen-production-hard-gate.yml" in text
    assert "      - production-gate" in text
    assert "needs.production-gate.result == 'success' || needs.production-gate.result == 'skipped'" in text
    assert "APROVO-PROD" in text
    assert "          - dev" in text and "          - stg" in text and "          - prod" in text
