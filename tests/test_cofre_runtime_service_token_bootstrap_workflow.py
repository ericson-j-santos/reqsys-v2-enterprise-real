from pathlib import Path

WORKFLOW = Path(".github/workflows/pc24x7-teams-token-bootstrap.yml")


def test_cofre_mode_reuses_canonical_workflow() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "mode:" in raw
    assert "- cofre-runtime" in raw
    assert "cofre:runtime_evidence" in raw
    assert "reqsys-cofre-runtime-evidence-service-token" in raw
    assert "/v1/cofre/runtime/control-status" in raw


def test_teams_mode_remains_default() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "default: teams" in raw
    assert "teams_gateway:ai_conversations" in raw
    assert "reqsys-pc24x7-teams-service-token" in raw
