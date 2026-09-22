from pathlib import Path

import yaml

from scripts.validate_bacen_prod_third_party_scope import validate


def write_scope(tmp_path: Path, vendors: list[dict]) -> Path:
    path = tmp_path / "scope.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "control_id": "BACEN-05",
                "scope": "prod",
                "mode": "fail_safe",
                "vendors": vendors,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def test_repository_scope_is_valid():
    result = validate(Path("governance/bacen/PROD-THIRD-PARTY-SCOPE.yaml"))
    assert result["ok"], result["errors"]
    assert result["vendor_count"] == 14
    assert result["counts"]["USED_IN_PROD"] == 3
    assert result["counts"]["NOT_USED_IN_PROD"] == 0
    assert result["counts"]["UNVERIFIED"] == 11
    assert result["local_evidence_verified_vendor_ids"] == ["T01", "T06", "T14"]
    assert result["remaining_unverified_count"] == 11
    assert result["evidence_reference_errors"] == []
    assert result["production_touched"] is False
    assert result["status_promotion_allowed"] is False


def test_not_used_requires_explicit_evidence(tmp_path):
    path = write_scope(
        tmp_path,
        [
            {"id": "T14", "name": "Fly.io", "classification": "USED_IN_PROD", "evidence": ["fly.toml"]},
            {"id": "T99", "name": "Example", "classification": "NOT_USED_IN_PROD", "evidence": []},
        ],
    )
    result = validate(path)
    assert not result["ok"]
    assert "T99: NOT_USED_IN_PROD requires explicit evidence" in result["errors"]


def test_used_requires_evidence(tmp_path):
    path = write_scope(
        tmp_path,
        [{"id": "T14", "name": "Fly.io", "classification": "USED_IN_PROD", "evidence": []}],
    )
    result = validate(path)
    assert not result["ok"]
    assert "T14: USED_IN_PROD requires evidence" in result["errors"]


def test_missing_evidence_path_fails_closed(tmp_path):
    path = write_scope(
        tmp_path,
        [
            {
                "id": "T14",
                "name": "Fly.io",
                "classification": "USED_IN_PROD",
                "evidence": ["governance/bacen/__missing_evidence__.yaml"],
            }
        ],
    )
    result = validate(path)
    assert not result["ok"]
    assert result["local_evidence_verified_vendor_ids"] == []
    assert result["evidence_reference_errors"] == [
        {
            "vendor_id": "T14",
            "reference": "governance/bacen/__missing_evidence__.yaml",
            "reason": "path_not_found",
        }
    ]


def test_evidence_path_cannot_escape_repository(tmp_path):
    path = write_scope(
        tmp_path,
        [
            {
                "id": "T14",
                "name": "Fly.io",
                "classification": "USED_IN_PROD",
                "evidence": ["../outside.txt"],
            }
        ],
    )
    result = validate(path)
    assert not result["ok"]
    assert result["evidence_reference_errors"][0]["reason"] == "path_outside_repository"


def test_unknown_classification_fails_closed(tmp_path):
    path = write_scope(
        tmp_path,
        [
            {"id": "T14", "name": "Fly.io", "classification": "USED_IN_PROD", "evidence": ["fly.toml"]},
            {"id": "T99", "name": "Example", "classification": "ASSUMED_UNUSED", "evidence": ["fly.toml"]},
        ],
    )
    result = validate(path)
    assert not result["ok"]
    assert any("invalid classification" in error for error in result["errors"])
