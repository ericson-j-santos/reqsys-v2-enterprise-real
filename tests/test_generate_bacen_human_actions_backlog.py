from pathlib import Path

import yaml

from scripts.generate_bacen_human_actions_backlog import build_backlog


def write_matrix(path: Path, controls: list[dict]) -> None:
    path.write_text(
        yaml.safe_dump({"controls": controls}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def control(
    control_id: str,
    *,
    lifecycle_stage: str | None = None,
    approval_status: str | None = None,
    institutional_governance_status: str | None = None,
) -> dict:
    payload = {
        "id": control_id,
        "title": f"Controle {control_id}",
        "domain": "governance",
        "status": "partial",
        "criticality": "critical",
        "owner": "GOVERNANCE",
        "evidence": f"artifacts/bacen/{control_id.lower()}.json",
        "next_stage": "continue_technical_evidence_until_production_gate",
        "production_touched": False,
    }
    if lifecycle_stage is not None:
        payload["lifecycle_stage"] = lifecycle_stage
    if approval_status is not None:
        payload["approval_status"] = approval_status
        payload["institutional_approval_gate_stage"] = "PRODUCTION"
    if institutional_governance_status is not None:
        payload["institutional_governance_status"] = institutional_governance_status
        payload["institutional_governance_gate_stage"] = "PRODUCTION"
    return payload


def test_development_deferred_controls_are_not_active_human_actions(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.yaml"
    write_matrix(
        matrix,
        [
            control(
                "BACEN-01",
                lifecycle_stage="DEVELOPMENT",
                approval_status="deferred_until_institutionalization",
            ),
            control(
                "BACEN-08",
                lifecycle_stage="DEVELOPMENT",
                institutional_governance_status="deferred_until_institutionalization",
            ),
            {
                **control("BACEN-02"),
                "next_stage": "complete_formal_quarterly_review",
            },
        ],
    )

    result = build_backlog(matrix)

    assert [item["control_id"] for item in result["items"]] == ["BACEN-02"]
    assert [item["control_id"] for item in result["deferred_items"]] == [
        "BACEN-01",
        "BACEN-08",
    ]
    assert result["summary"]["pending_controls"] == 1
    assert result["summary"]["deferred_controls"] == 2
    assert result["human_action_required"] is True
    assert all(
        item["human_action_required_now"] is False
        for item in result["deferred_items"]
    )


def test_only_deferred_controls_produce_no_current_human_action(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.yaml"
    write_matrix(
        matrix,
        [
            control(
                "BACEN-01",
                lifecycle_stage="DEVELOPMENT",
                approval_status="deferred_until_institutionalization",
            ),
            control(
                "BACEN-08",
                lifecycle_stage="DEVELOPMENT",
                institutional_governance_status="deferred_until_institutionalization",
            ),
        ],
    )

    result = build_backlog(matrix)

    assert result["items"] == []
    assert result["summary"]["pending_controls"] == 0
    assert result["summary"]["deferred_controls"] == 2
    assert result["human_action_required"] is False
    assert result["next_stage"] == "continue_technical_evidence_until_institutional_gate"


def test_production_reactivates_deferred_control_as_human_action(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.yaml"
    write_matrix(
        matrix,
        [
            control(
                "BACEN-08",
                lifecycle_stage="PRODUCTION",
                institutional_governance_status="deferred_until_institutionalization",
            )
        ],
    )

    result = build_backlog(matrix)

    assert [item["control_id"] for item in result["items"]] == ["BACEN-08"]
    assert result["deferred_items"] == []
    assert result["human_action_required"] is True
    assert result["items"][0]["human_action_required_now"] is True
    assert result["items"][0]["institutional_gate_stage"] == "PRODUCTION"
