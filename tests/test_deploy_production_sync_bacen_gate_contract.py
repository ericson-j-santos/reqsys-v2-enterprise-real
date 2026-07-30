from pathlib import Path


WORKFLOW = Path(".github/workflows/deploy-production-sync.yml")


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_bacen_gate_precedes_every_production_capability():
    text = workflow_text()
    gate = text.index("Gerar decisão BACEN de produção")
    environment = text.index("environment: production")
    secret = text.index("secrets.FLY_API_TOKEN")
    deploy = text.index("flyctl deploy")

    assert "REQSYS_PRODUCTION_GOVERNANCE_GATE" in text
    assert "--scope prod" in text
    assert gate < environment
    assert gate < secret
    assert gate < deploy


def test_automatic_push_skips_production_without_false_red():
    text = workflow_text()
    assert "outputs:" in text
    assert "production_allowed:" in text
    assert "needs.gate.outputs.production_allowed == 'true'" in text
    assert "github.event_name == 'workflow_dispatch'" in text
    assert "Falhar solicitação manual não autorizada" in text


def test_all_mutating_jobs_depend_on_gate_authorization():
    text = workflow_text()
    for job_name in (
        "configure-prod-secrets:",
        "deploy-backend:",
        "deploy-frontend:",
    ):
        start = text.index(job_name)
        next_job = text.find("\n  ", start + len(job_name))
        block = text[start:] if next_job == -1 else text[start:next_job]
        assert "needs.gate.outputs.production_allowed == 'true'" in block


def test_blocked_path_does_not_materialize_teams_secret():
    text = workflow_text()
    notification = text.index("Notificar Teams (ambiente produção)")
    secret = text.index("secrets.TEAMS_GATEWAY_DESTINO_ID", notification)
    protected_block = text[notification:secret]
    assert "if: needs.gate.outputs.production_allowed == 'true'" in protected_block


def test_bacen_decision_is_retained_for_audit():
    text = workflow_text()
    assert "bacen-production-hard-gate-deploy-sync" in text
    assert "retention-days: 365" in text
    assert "production_touched" in text
