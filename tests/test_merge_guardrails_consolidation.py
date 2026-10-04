from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_merge_guardrails_reutilizam_controles_canonicos_sem_workflow_duplicado() -> None:
    template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
    doc = (ROOT / "docs/governanca/MERGE_GUARDRAILS.md").read_text(encoding="utf-8")
    policy = json.loads(
        (ROOT / "governance/merge/current-sha-required-workflows.json").read_text(encoding="utf-8")
    )
    queue = (ROOT / ".github/workflows/governed-merge-queue.yml").read_text(encoding="utf-8")

    assert "## Integração governada" in template
    assert "behind_by=0" in template
    assert "HEAD atual" in template
    assert "expected_head_sha" in doc
    assert "Pre-PR Readiness Gate" in policy["required_workflows"]
    assert "EXPECTED_HEAD_SHA" in queue
    assert not (ROOT / ".github/workflows/merge-guardrails.yml").exists()
