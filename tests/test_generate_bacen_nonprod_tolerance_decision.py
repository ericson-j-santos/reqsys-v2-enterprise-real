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



def test_real_policy_window_boundary_and_prod_are_fail_closed(tmp_path: Path) -> None:
    """Check the versioned policy, including the first day after expiry."""
    from datetime import date, timedelta

    policy = Path("governance/bacen/NONPROD-TEMPORARY-TOLERANCE-POLICY.yaml")
    config = yaml.safe_load(policy.read_text(encoding="utf-8"))
    activation = config["activation"]
    start = date.fromisoformat(str(activation["valid_from"]))
    end = date.fromisoformat(str(activation["valid_until"]))

    assert start <= end
    assert (end - start).days <= config["maximum_review_window_days"]
    assert activation["renewal_requires_explicit_policy_change"] is True
    assert set(config["allowed_scopes"]) == {"pull_request", "dev", "stg"}
    assert set(config["blocked_scopes"]) == {"prod"}
    assert config["production_touched"] is False
    assert config["requirements"]["prohibit_fabricated_approvals"] is True
    assert config["requirements"]["prohibit_fabricated_evidence"] is True
    assert config["requirements"]["preserve_control_status"] is True

    controlled = ("BACEN-01", "BACEN-02", "BACEN-05", "BACEN-08")
    matrix = tmp_path / "matrix.yaml"
    write_yaml(matrix, {
        "controls": [
            {"id": control_id, "status": "partial", "production_touched": False}
            for control_id in controlled
        ]
    })
    original_matrix = matrix.read_bytes()
    original_policy = policy.read_bytes()

    for scope in ("pull_request", "dev", "stg"):
        for day in (start, end):
            observed = build_decision(
                matrix, policy, scope, now=datetime.combine(day, datetime.min.time(), UTC)
            )
            assert observed["decision"] == "allow"
            assert observed["policy_active"] is True
            assert observed["valid_until"] == end.isoformat()
            assert observed["tolerated_controls"] == list(controlled)
            assert observed["production_deployment_allowed"] is False
            assert observed["preserved_control_status"] is True
            assert observed["human_action_required"] is True

        for day, expected in (
            (start - timedelta(days=1), "temporary_tolerance_not_active_yet"),
            (end + timedelta(days=1), "temporary_tolerance_expired"),
        ):
            observed = build_decision(
                matrix, policy, scope, now=datetime.combine(day, datetime.min.time(), UTC)
            )
            assert observed["decision"] == "block"
            assert observed["policy_active"] is False
            assert expected in observed["structural_findings"]
            assert observed["blocking_controls"] == list(controlled)
            assert observed["production_deployment_allowed"] is False

    for day in (start, end, end + timedelta(days=1)):
        observed = build_decision(
            matrix, policy, "prod", now=datetime.combine(day, datetime.min.time(), UTC)
        )
        assert observed["decision"] == "block"
        assert observed["blocking_controls"] == list(controlled)
        assert observed["production_deployment_allowed"] is False

    assert matrix.read_bytes() == original_matrix
    assert policy.read_bytes() == original_policy
