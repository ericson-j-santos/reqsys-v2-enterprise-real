from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_existe_um_unico_workflow_de_commit_para_teams() -> None:
    legacy = WORKFLOWS / "notify-teams-repo-changes.yml"
    canonical = WORKFLOWS / "teams-commit-notification.yml"

    assert not legacy.exists(), "workflow legado volta a duplicar cada push em main"
    assert canonical.exists()

    candidates: list[str] = []
    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        if "ReqSys — novo commit" in text or "ReqSys - Novo commit em main" in text:
            candidates.append(path.name)

    assert candidates == ["teams-commit-notification.yml"]


def test_atualizacao_do_flow_e_aplicada_apos_merge_em_main() -> None:
    workflow = (WORKFLOWS / "teams-v2-adaptive-card-update.yml").read_text(encoding="utf-8")

    assert "branches: [main]" in workflow
    assert 'scripts/update_teams_v2_adaptive_card.py' in workflow
    assert "APPLY_CHANGE: ${{ github.event_name == 'push' || inputs.apply == true }}" in workflow
    assert "UPDATE-REQSYS-TEAMSV2-CARD" in workflow
