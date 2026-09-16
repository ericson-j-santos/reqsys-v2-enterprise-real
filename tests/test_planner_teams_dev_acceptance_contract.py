from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "planner_teams_dev_acceptance_v2.mjs"


def test_acceptance_keeps_flows_started_after_proof() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "flowAction(environmentId, flowId, 'stop'" not in source
    assert "flow_final_state" in source
    assert "postconditions" in source
    assert "started_confirmed" in source


def test_acceptance_preserves_positive_and_negative_controls() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "REQSYS-E2E-NOTIFY-FILTER-" in source
    assert "REQSYS-NOTIFY-FILTER-NORMAL-" in source
    assert "expected_teams: 'skipped'" in source
    assert "expected_teams: 'succeeded'" in source
