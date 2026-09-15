from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/pending-development-agent-pr.yml"


def load_workflow() -> dict:
    # PyYAML 1.1 interpreta a chave `on` como boolean; BaseLoader preserva o contrato textual.
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_agent_pr_waits_for_successful_pre_pr_readiness() -> None:
    workflow = load_workflow()

    assert workflow["on"]["workflow_run"]["workflows"] == ["Pre-PR Readiness Gate"]
    assert workflow["on"]["workflow_run"]["types"] == ["completed"]
    condition = workflow["jobs"]["open-governed-pr"]["if"]
    assert "workflow_run.conclusion == 'success'" in condition
    assert "startsWith(github.event.workflow_run.head_branch, 'copilot/')" in condition


def test_agent_pr_is_bound_to_the_validated_sha_and_branch() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    # Nunca fazer checkout e executar código controlado pela branch do agente
    # em um workflow_run com token capaz de criar PR.
    assert "ref: ${{ github.event.workflow_run.head_sha }}" not in workflow_text
    assert "GITHUB_SHA: ${{ github.event.workflow_run.head_sha }}" in workflow_text
    assert '--branch "${{ github.event.workflow_run.head_branch }}"' in workflow_text
    assert "READY_FOR_PR_WAIT_SECONDS: \"0\"" in workflow_text


def test_agent_pr_has_only_the_required_write_permissions() -> None:
    permissions = load_workflow()["permissions"]

    assert permissions == {
        "actions": "read",
        "contents": "read",
        "issues": "write",
        "pull-requests": "write",
    }
