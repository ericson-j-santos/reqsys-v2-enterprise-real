from pathlib import Path

import yaml

from scripts.generate_bacen_nonprod_tolerance_decision import build_decision


WORKFLOW = Path(".github/workflows/bacen-production-hard-gate.yml")


def write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def policy() -> dict:
    return {
        "mode": "temporary_nonprod_tolerance",
        "allowed_scopes": ["pull_request", "dev", "stg"],
        "blocked_scopes": ["prod"],
        "allowed_control_statuses": ["implemented", "partial"],
        "always_block_statuses": ["gap"],
        "maximum_review_window_days": 30,
        "valid_from": "2026-07-30",
        "valid_until": "2026-08-29",
        "review_owner_role": "GOVERNANCE",
        "renewal_requires_explicit_policy_change": True,
    }


def test_reusable_workflow_enforces_before_production_access():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_call:" in text
    assert "--scope prod" in text
    assert "production_deployment_allowed" in text
    assert "Enforce production authorization" in text
    assert "secrets." not in text
    assert "environment: production" not in text


def test_partial_control_blocks_production(tmp_path):
    matrix_path = tmp_path / "matrix.yml"
    policy_path = tmp_path / "policy.yml"
    write_yaml(
        matrix_path,
        {
            "controls": [
                {
                    "id": "BACEN-08",
                    "status": "partial",
                    "criticality": "critical",
                    "production_touched": False,
                }
            ]
        },
    )
    write_yaml(policy_path, policy())

    decision = build_decision(matrix_path, policy_path, "prod")
    assert decision["decision"] == "block"
    assert decision["production_deployment_allowed"] is False
    assert decision["blocking_controls"] == ["BACEN-08"]


def test_all_implemented_controls_allow_production(tmp_path):
    matrix_path = tmp_path / "matrix.yml"
    policy_path = tmp_path / "policy.yml"
    write_yaml(
        matrix_path,
        {
            "controls": [
                {
                    "id": "BACEN-08",
                    "status": "implemented",
                    "criticality": "critical",
                    "production_touched": False,
                }
            ]
        },
    )
    write_yaml(policy_path, policy())

    decision = build_decision(matrix_path, policy_path, "prod")
    assert decision["decision"] == "allow"
    assert decision["production_deployment_allowed"] is True
    assert decision["blocking_controls"] == []
