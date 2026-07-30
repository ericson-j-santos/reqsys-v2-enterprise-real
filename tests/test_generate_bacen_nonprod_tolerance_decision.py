from datetime import UTC, datetime
from pathlib import Path

import yaml

from scripts.generate_bacen_nonprod_tolerance_decision import build_decision


def write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def matrix_payload() -> dict:
    return {
        "controls": [
            {
                "id": "BACEN-01",
                "status": "partial",
                "criticality": "critical",
                "production_touched": False,
            },
            {
                "id": "BACEN-03",
                "status": "implemented",
                "criticality": "critical",
                "production_touched": False,
            },
        ]
    }


def policy_payload() -> dict:
    return {
        "activation": {
            "valid_from": "2026-07-30",
            "valid_until": "2026-08-29",
            "review_owner_role": "GOVERNANCE",
            "renewal_requires_explicit_policy_change": True,
        },
        "allowed_scopes": ["pull_request", "dev", "stg"],
        "blocked_scopes": ["prod"],
        "allowed_control_statuses": ["implemented", "partial"],
        "always_block_statuses": ["gap"],
        "maximum_review_window_days": 30,
    }


def test_active_tolerance_allows_nonprod_and_preserves_partial(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.yaml"
    policy = tmp_path / "policy.yaml"
    write_yaml(matrix, matrix_payload())
    write_yaml(policy, policy_payload())

    result = build_decision(
        matrix,
        policy,
        "stg",
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )

    assert result["decision"] == "allow"
    assert result["policy_active"] is True
    assert result["valid_until"] == "2026-08-29"
    assert result["review_deadline"] == "2026-08-29"
    assert result["tolerated_controls"] == ["BACEN-01"]
    assert result["preserved_control_status"] is True


def test_expired_tolerance_blocks_nonprod(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.yaml"
    policy = tmp_path / "policy.yaml"
    write_yaml(matrix, matrix_payload())
    write_yaml(policy, policy_payload())

    result = build_decision(
        matrix,
        policy,
        "dev",
        now=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert result["decision"] == "block"
    assert result["policy_active"] is False
    assert "temporary_tolerance_expired" in result["structural_findings"]
    assert result["blocking_controls"] == ["BACEN-01"]


def test_prod_blocks_partial_even_during_active_window(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.yaml"
    policy = tmp_path / "policy.yaml"
    write_yaml(matrix, matrix_payload())
    write_yaml(policy, policy_payload())

    result = build_decision(
        matrix,
        policy,
        "prod",
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )

    assert result["decision"] == "block"
    assert result["production_deployment_allowed"] is False
    assert result["blocking_controls"] == ["BACEN-01"]
