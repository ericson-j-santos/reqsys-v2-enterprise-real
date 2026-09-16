from pathlib import Path


WORKFLOW = Path(".github/workflows/auto-public-runtime-evidence.yml")
RUNBOOK = Path("docs/runbooks/auto-public-runtime-evidence.md")


def test_auto_public_runtime_uses_ephemeral_github_token() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "actions: write" in workflow
    assert "GH_TOKEN: ${{ github.token }}" in workflow
    assert "gh workflow run public-runtime-evidence.yml" in workflow
    assert "GH_PAT_ACTIONS" not in workflow
    assert "secrets.GH_PAT_ACTIONS" not in workflow


def test_auto_public_runtime_runbook_matches_ephemeral_contract() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "GITHUB_TOKEN" in runbook
    assert "actions: write" in runbook
    assert "GH_PAT_ACTIONS não faz parte deste contrato" in runbook
    assert "PAT persistente" in runbook
