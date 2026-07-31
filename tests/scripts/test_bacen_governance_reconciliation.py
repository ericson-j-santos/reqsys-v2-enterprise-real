from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "governance/bacen/BACEN-CONTROL-MATRIX.yaml"
RECONCILIATION_PATH = (
    REPO_ROOT / "governance/bacen/BACEN-GOVERNANCE-RECONCILIATION.yaml"
)
COORDINATION_PATH = REPO_ROOT / "docs/governance/REQSYS_MULTI_AI_COORDINATION.md"


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_approval_comments_do_not_promote_bacen_controls() -> None:
    matrix = _load_yaml(MATRIX_PATH)
    reconciliation = _load_yaml(RECONCILIATION_PATH)

    controls = {item["id"]: item for item in matrix["controls"]}
    decisions = {item["control_id"]: item for item in reconciliation["controls"]}

    for control_id in ("BACEN-01", "BACEN-08"):
        assert controls[control_id]["status"] == "partial"
        assert controls[control_id]["decision_evidence"] == (
            "governance/bacen/BACEN-GOVERNANCE-RECONCILIATION.yaml"
        )
        assert decisions[control_id]["decision_evidence_recorded"] is True
        assert decisions[control_id]["promote_control_status"] is False
        assert decisions[control_id]["closure_ready"] is False
        assert decisions[control_id]["blockers"]

    assert reconciliation["summary"]["approvals_recorded"] == 2
    assert reconciliation["summary"]["controls_promoted"] == 0
    assert reconciliation["production_touched"] is False


def test_historical_multi_ai_branches_are_not_merge_candidates() -> None:
    coordination = COORDINATION_PATH.read_text(encoding="utf-8")

    for branch in ("ai/runtime-public", "ai/observability", "ai/ux-operacional"):
        assert f"`{branch}`" in coordination

    assert "`superseded`" in coordination
    assert "não fazer merge ou rebase" in coordination
    assert "agent/reqsys-001-governance-reconciliation-v1" in coordination
