from pathlib import Path


WORKFLOW = Path(".github/workflows/configurar-fly-auth-azure.yml")


def test_production_gate_precedes_flyctl_and_secrets():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "REQSYS_PRODUCTION_GOVERNANCE_GATE" in text
    assert text.count("--scope prod") == 2

    first_gate = text.index("Gate BACEN antes de configurar produção")
    first_flyctl = text.index("Instalar flyctl")
    first_secret = text.index("secrets.FLY_API_TOKEN")
    assert first_gate < first_flyctl < first_secret


def test_only_production_cells_execute_the_gate():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "if: inputs.app_env == 'production'" in text
    assert "if: matrix.environment == 'production'" in text
    assert "environment: staging" in text
    assert "environment: development" in text


def test_gate_evidence_is_retained_without_touching_production():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "retention-days: 365" in text
    assert "bacen-production-hard-gate-auth-manual" in text
    assert "bacen-production-hard-gate-auth-production" in text
