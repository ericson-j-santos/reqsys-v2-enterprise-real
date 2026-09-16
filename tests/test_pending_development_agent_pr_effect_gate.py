from pathlib import Path


WORKFLOW = Path(".github/workflows/pending-development-agent-pr.yml")


def test_pending_agent_pr_requires_real_external_effect() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Validar efeito real da abertura governada" in text
    assert "artifacts/auto-pr-request/auto-pr-request.json" in text
    assert 'allowed = {"created", "updated", "skipped_merged"}' in text
    assert "auto_pr_effect_not_applied" in text
    assert "auto_pr_effect_incomplete" in text


def test_pending_agent_pr_still_publishes_evidence_on_failure() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    evidence = text.split("- name: Publicar evidência", 1)[1]

    assert "if: always()" in evidence
    assert "pending-development-agent-pr-${{ github.event.workflow_run.head_sha }}" in evidence
